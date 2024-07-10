import logging
from enum import Enum
from io import BytesIO
from typing import Optional

from anyio import fail_after
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from PIL import Image
from pydantic import BaseModel

from crynux_server.models import TaskType
from crynux_server.worker_manager import (TaskError, TaskExecutionError,
                                          TaskInput, TaskInvalid, TaskResult,
                                          WorkerManager, is_task_invalid)

from ..depends import WorkerManagerDep

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/worker")


class WorkerPhase(str, Enum):
    Prefetch = "prefetch"
    InitInference = "init_inference"
    Inference = "inference"


class WorkerPhaseMessage(BaseModel):
    phase: WorkerPhase


class PayloadType(str, Enum):
    Text = "text"
    Json = "json"
    PNG = "png"
    Error = "error"


class WorkerPayloadMessage(BaseModel):
    worker_phase: WorkerPhase
    has_payload: bool
    has_next: bool
    payload_type: Optional[PayloadType] = None


async def process_prefetch(
    worker_id: int, websocket: WebSocket, worker_manager: WorkerManager
):
    await worker_manager.start_prefetch_task(worker_id)
    try:
        while True:
            raw_msg = await websocket.receive_json()
            msg = WorkerPayloadMessage.model_validate(raw_msg)
            assert msg.worker_phase == WorkerPhase.Prefetch
            if msg.has_payload:
                assert msg.payload_type is not None
                if msg.payload_type == PayloadType.Text:
                    progress = await websocket.receive_text()
                    await worker_manager.push_prefetch_task_progress(
                        worker_id, progress
                    )
                    _logger.info(f"worker {worker_id} prefetching models: {progress}")
                elif msg.payload_type == PayloadType.Error:
                    err_msg = await websocket.receive_text()
                    worker_manager.prefetch_task_error(worker_id, err_msg)
                    _logger.error(
                        f"worker {worker_id} prefetching models error:\n{err_msg}"
                    )
                    return
                else:
                    raise ValueError(
                        f"worker {worker_id} incorrect payload type {msg.payload_type} in prefetch phase"
                    )
            if not msg.has_next:
                break
        worker_manager.finish_prefetch_task(worker_id)
        _logger.info(f"worker {worker_id} complete prefetching models")
    except WebSocketDisconnect:
        _logger.error(f"worker {worker_id} disconnects during prefetching models")
        worker_manager.cancel_prefetch_task(worker_id)
        raise
    except Exception as e:
        _logger.exception(e)
        _logger.error(f"worker {worker_id} prefetching models unexpected error")
        worker_manager.init_inference_task_error(
            worker_id, f"unexpected error: {str(e)}"
        )
        raise e


async def process_init_inference(
    worker_id: int, websocket: WebSocket, worker_manager: WorkerManager
):
    await worker_manager.start_init_inference_task(worker_id)
    try:
        raw_msg = await websocket.receive_json()
        msg = WorkerPayloadMessage.model_validate(raw_msg)
        assert msg.worker_phase == WorkerPhase.InitInference
        assert not msg.has_next
        if msg.has_payload:
            assert msg.payload_type is not None
            if msg.payload_type != PayloadType.Error:
                raise ValueError(
                    f"worker {worker_id} incorrect payload type {msg.payload_type} in init inference phase"
                )
            err_msg = await websocket.receive_text()
            worker_manager.init_inference_task_error(worker_id, err_msg)
            _logger.error(f"worker {worker_id} init inference task error:\n{err_msg}")
            return
        else:
            worker_manager.init_inference_task_success(worker_id)
            _logger.info(f"worker {worker_id} complete init inference task")
    except WebSocketDisconnect:
        _logger.error(f"worker {worker_id} disconnects during running initial inference task")
        worker_manager.cancel_init_inference_task(worker_id)
        raise
    except Exception as e:
        _logger.exception(e)
        _logger.error(f"worker {worker_id} init inference task unexpected error")
        worker_manager.init_inference_task_error(
            worker_id, f"unexpected error: {str(e)}"
        )
        raise e


async def _process_one_inference_task(
    worker_id: int,
    websocket: WebSocket,
    task_input: TaskInput,
    task_result: TaskResult,
):
    try:
        await websocket.send_json(task_input.model_dump())
        resp = await websocket.receive_text()
        assert resp == "task received"
        results = []
        while True:
            raw_msg = await websocket.receive_json()
            msg = WorkerPayloadMessage.model_validate(raw_msg)
            assert msg.worker_phase == WorkerPhase.Inference
            if msg.has_payload:
                assert msg.payload_type is not None
                if msg.payload_type == PayloadType.Error:
                    err_msg = await websocket.receive_text()
                    if is_task_invalid(err_msg):
                        exc = TaskInvalid(err_msg)
                    else:
                        exc = TaskExecutionError(err_msg)
                    task_result.set_error(exc)
                    _logger.error(
                        f"worker {worker_id} inference task {task_input.task_id} error:\n{err_msg}"
                    )
                    return
                elif msg.payload_type == PayloadType.PNG:
                    assert task_input.task_type == TaskType.SD
                    img_bytes = await websocket.receive_bytes()
                    img_f = BytesIO(img_bytes)
                    img = Image.open(img_f)
                    results.append(img)
                elif msg.payload_type == PayloadType.Json:
                    assert task_input.task_type == TaskType.LLM
                    res = await websocket.receive_json()
                    results.append(res)
            if not msg.has_next:
                break
        task_result.set_result(results)
    except WebSocketDisconnect:
        _logger.error(f"worker {worker_id} disconnects, cancel inference task {task_input.task_id}")
        task_result.cancel()
        raise
    except Exception as e:
        _logger.exception(e)
        _logger.error(
            f"worker {worker_id} inferece task {task_input.task_id} unexpected error"
        )
        task_result.set_error(TaskError(f"unexpected error: {str(e)}"))
        raise e


async def process_inference(
    worker_id: int, websocket: WebSocket, worker_manager: WorkerManager
):
    while True:
        try:
            with fail_after(1):
                task_input, task_result = await worker_manager.get_task(worker_id)
        except TimeoutError:
            try:
                await websocket.send_text("")
                resp = await websocket.receive_text()
                assert resp == "task received"
                continue
            except WebSocketDisconnect:
                raise
        await _process_one_inference_task(worker_id, websocket, task_input, task_result)


@router.websocket("/")
async def worker(websocket: WebSocket, worker_manager: WorkerManagerDep):
    await websocket.accept()
    version_msg = await websocket.receive_json()
    version = version_msg["version"]
    worker_id = worker_manager.connect(version)
    await websocket.send_json({"worker_id": worker_id})
    try:
        while True:
            raw_status_msg = await websocket.receive_json()
            phase = WorkerPhaseMessage.model_validate(raw_status_msg).phase
            if phase == WorkerPhase.Prefetch:
                await process_prefetch(worker_id, websocket, worker_manager)
            elif phase == WorkerPhase.InitInference:
                await process_init_inference(worker_id, websocket, worker_manager)
            else:
                await process_inference(worker_id, websocket, worker_manager)
    except WebSocketDisconnect:
        pass
    finally:
        worker_manager.disconnect(worker_id)
