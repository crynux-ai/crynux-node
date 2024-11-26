import json
import os
import tempfile
import shutil
from contextlib import ExitStack
from typing import BinaryIO, List, Optional, Dict, Any

import httpx
from anyio import wrap_file, to_thread, open_file

from crynux_server.models import RelayTask

from .abc import Relay
from .exceptions import RelayError
from .sign import Signer


def _process_resp(resp: httpx.Response, method: str):
    try:
        resp.raise_for_status()
        return resp
    except httpx.HTTPStatusError as e:
        message = str(e)
        if resp.status_code == 400:
            try:
                content = resp.json()
                if "data" in content:
                    data = content["data"]
                    message = json.dumps(data)
                elif "message" in content:
                    message = content["message"]
                else:
                    message = resp.text
            except Exception:
                pass
        raise RelayError(resp.status_code, method, message) from e


class WebRelay(Relay):
    def __init__(self, base_url: str, privkey: str) -> None:
        super().__init__()
        self.client = httpx.AsyncClient(base_url=base_url, timeout=30)
        self.signer = Signer(privkey=privkey)

    async def create_task(self, task_id_commitment: bytes, task_args: str, checkpoint_dir: Optional[str] = None) -> RelayTask:
        input: Dict[str, Any] = {"task_id_commitment": task_id_commitment.hex(), "task_args": task_args}
        timestamp, signature = self.signer.sign(input)
        input.update({"timestamp": timestamp, "signature": signature})

        if checkpoint_dir is not None:
            with tempfile.TemporaryDirectory() as tmp_dir:
                checkpoint_file = os.path.join(tmp_dir, "checkpoint.zip")
                await to_thread.run_sync(
                    shutil.make_archive, checkpoint_file[:-4], "zip", checkpoint_dir
                )
            with ExitStack() as stack:
                filename = os.path.basename(checkpoint_file)
                file_obj = stack.enter_context(open(checkpoint_file, "rb"))
                files = [("checkpoint", (filename, file_obj))]
                
                resp = await self.client.post(f"/v1/inference_tasks/{task_id_commitment.hex()}", data=input, files=files, timeout=None)
        else:
            resp = await self.client.post(f"/v1/inference_tasks/{task_id_commitment.hex()}", data=input)
        resp = _process_resp(resp, "createTask")
        content = resp.json()
        data = content["data"]
        return RelayTask.model_validate(data)

    async def get_checkpoint(self, task_id_commitment: bytes, result_checkpoint_dir: str):
        input = {"task_id_commitment": task_id_commitment.hex()}
        timestamp, signature = self.signer.sign(input)

        with tempfile.TemporaryDirectory() as tmp_dir:
            checkpoint_file = os.path.join(tmp_dir, "checkpoint.zip")
            async with await open_file(checkpoint_file, mode="wb") as f:
                resp = await self.client.get(
                    f"/v1/inference_tasks/{task_id_commitment.hex()}/checkpoint",
                    params={"timestamp": timestamp, "signature": signature},
                )
                resp = _process_resp(resp, "getCheckpoint")
                async for chunk in resp.aiter_bytes(4096):
                    await f.write(chunk)

            await to_thread.run_sync(
                shutil.unpack_archive, checkpoint_file, result_checkpoint_dir
            )

    async def get_task(self, task_id_commitment: bytes) -> RelayTask:
        input = {"task_id_commitment": task_id_commitment.hex()}
        timestamp, signature = self.signer.sign(input)

        resp = await self.client.get(
            f"/v1/inference_tasks/{task_id_commitment.hex()}",
            params={"timestamp": timestamp, "signature": signature},
        )
        resp = _process_resp(resp, "getTask")
        content = resp.json()
        data = content["data"]
        return RelayTask.model_validate(data)

    async def upload_task_result(self, task_id_commitment: bytes, file_paths: List[str], checkpoint_dir: Optional[str] = None):
        input = {"task_id_commitment": task_id_commitment.hex()}
        timestamp, signature = self.signer.sign(input)

        with ExitStack() as stack:
            files = []
            for file_path in file_paths:
                filename = os.path.basename(file_path)
                file_obj = stack.enter_context(open(file_path, "rb"))
                files.append(("images", (filename, file_obj)))

            if checkpoint_dir is not None:
                tmp_dir = stack.enter_context(tempfile.TemporaryDirectory())
                checkpoint_file = os.path.join(tmp_dir, "checkpoint.zip")
                await to_thread.run_sync(shutil.make_archive, checkpoint_file[:-4], "zip", checkpoint_dir)
                filename = os.path.basename(checkpoint_file)
                file_obj = stack.enter_context(open(checkpoint_file, "rb"))
                files.append(("checkpoint", (filename, file_obj)))

            # disable timeout because there may be many images or image size may be very large
            resp = await self.client.post(
                f"/v1/inference_tasks/{task_id_commitment.hex()}/results",
                data={"timestamp": timestamp, "signature": signature},
                files=files,
                timeout=None
            )
            resp = _process_resp(resp, "uploadTaskResult")
            content = resp.json()
            message = content["message"]
            if message != "success":
                raise RelayError(resp.status_code, "uploadTaskResult", message)

    async def get_result(self, task_id_commitment: bytes, index: int, dst: BinaryIO):
        input = {"task_id_commitment": task_id_commitment.hex(), "image_num": str(index)}
        timestamp, signature = self.signer.sign(input)

        async_dst = wrap_file(dst)

        async with self.client.stream(
            "GET",
            f"/v1/inference_tasks/{task_id_commitment.hex()}/results/{index}",
            params={"timestamp": timestamp, "signature": signature},
        ) as resp:
            resp = _process_resp(resp, "getTask")
            async for chunk in resp.aiter_bytes():
                await async_dst.write(chunk)

    async def get_result_checkpoint(self, task_id_commitment: bytes, result_checkpoint_dir: str):
        input = {"task_id_commitment": task_id_commitment.hex()}
        timestamp, signature = self.signer.sign(input)

        with tempfile.TemporaryDirectory() as tmp_dir:
            checkpoint_file = os.path.join(tmp_dir, "checkpoint.zip")
            async with await open_file(checkpoint_file, mode="wb") as f:
                resp = await self.client.get(
                    f"/v1/inference_tasks/{task_id_commitment.hex()}/results/checkpoint",
                    params={"timestamp": timestamp, "signature": signature},
                )
                resp = _process_resp(resp, "getResultCheckpoint")
                async for chunk in resp.aiter_bytes(4096):
                    await f.write(chunk)

            await to_thread.run_sync(
                shutil.unpack_archive, checkpoint_file, result_checkpoint_dir
            )

    async def now(self) -> int:
        resp = await self.client.get("/v1/now")
        resp = _process_resp(resp, "now")
        content = resp.json()
        data = content["data"]
        now = data["now"]
        return now

    async def close(self):
        await self.client.aclose()
