import json
import os
import tempfile
import shutil
from contextlib import ExitStack
from typing import BinaryIO, List, Optional, Dict, Any

from hexbytes import HexBytes
import httpx
from anyio import wrap_file, to_thread, open_file

from crynux_server.models import ChainTask, TaskError, TaskAbortReason
from crynux_server.models.node import ChainNodeStatus, NodeInfo
from crynux_server.models.task import RelayTask

from .abc import Relay
from .exceptions import RelayError
from .sign import Signer

from eth_account import Account
from eth_account.signers.local import LocalAccount
from eth_typing import ChecksumAddress
from eth_utils import to_checksum_address

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

def _get_address_from_privkey(privkey: str) -> ChecksumAddress:
    addrLowcase = Account.from_key(privkey).address
    return to_checksum_address(addrLowcase)

class WebRelay(Relay):
    def __init__(self, base_url: str, privkey: str) -> None:
        super().__init__()
        self.client = httpx.AsyncClient(base_url=base_url, timeout=30)
        self.signer = Signer(privkey=privkey)
        self.node_address = _get_address_from_privkey(privkey)


    """ task related """

    async def create_task(self, task_id_commitment: bytes, task_args: str, checkpoint_dir: Optional[str] = None) -> RelayTask:
        task_id_commitment_hex = HexBytes(task_id_commitment).hex()
        input: Dict[str, Any] = {"task_id_commitment": task_id_commitment_hex, "task_args": task_args}
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
                
                resp = await self.client.post(f"/v1/inference_tasks/{task_id_commitment_hex}", data=input, files=files, timeout=None)
        else:
            resp = await self.client.post(f"/v1/inference_tasks/{task_id_commitment_hex}", data=input)
        resp = _process_resp(resp, "createTask")
        content = resp.json()
        data = content["data"]
        return RelayTask.model_validate(data)

    async def get_checkpoint(self, task_id_commitment: bytes, result_checkpoint_dir: str):
        task_id_commitment_hex = HexBytes(task_id_commitment).hex()
        input = {"task_id_commitment": task_id_commitment_hex}
        timestamp, signature = self.signer.sign(input)

        with tempfile.TemporaryDirectory() as tmp_dir:
            checkpoint_file = os.path.join(tmp_dir, "checkpoint.zip")
            async with await open_file(checkpoint_file, mode="wb") as f:
                resp = await self.client.get(
                    f"/v1/inference_tasks/{task_id_commitment_hex}/checkpoint",
                    params={"timestamp": timestamp, "signature": signature},
                )
                resp = _process_resp(resp, "getCheckpoint")
                async for chunk in resp.aiter_bytes(4096):
                    await f.write(chunk)

            await to_thread.run_sync(
                shutil.unpack_archive, checkpoint_file, result_checkpoint_dir
            )

    async def get_task(self, task_id_commitment: bytes) -> RelayTask:
        task_id_commitment_hex = HexBytes(task_id_commitment).hex()
        input = {"task_id_commitment": task_id_commitment_hex}
        timestamp, signature = self.signer.sign(input)

        resp = await self.client.get(
            f"/v1/inference_tasks/{task_id_commitment_hex}",
            params={"timestamp": timestamp, "signature": signature},
        )
        resp = _process_resp(resp, "getTask")
        content = resp.json()
        data = content["data"]
        return RelayTask.model_validate(data)

    async def report_task_error(self, task_id_commitment: bytes, task_error: TaskError):
        task_id_commitment_hex = HexBytes(task_id_commitment).hex()
        input = {"task_id_commitment": task_id_commitment_hex}
        timestamp, signature = self.signer.sign(input)

        resp = await self.client.post(
            f"/v1/inference_tasks/{task_id_commitment_hex}/task_error",
            params={"task_error": task_error, "timestamp": timestamp, "signature": signature},
        )
        resp = _process_resp(resp, "reportTaskError")

    async def submit_task_score(self, task_id_commitment: bytes, score: bytes):
        task_id_commitment_hex = HexBytes(task_id_commitment).hex()
        input = {"task_id_commitment": task_id_commitment_hex}
        timestamp, signature = self.signer.sign(input)

        resp = await self.client.post(
            f"/v1/inference_tasks/{task_id_commitment_hex}/score",
            params={"score": score, "timestamp": timestamp, "signature": signature},
        )
        resp = _process_resp(resp, "reportTaskError")

    async def abort_task(self, task_id_commitment: bytes, abort_reason: TaskAbortReason):
        task_id_commitment_hex = HexBytes(task_id_commitment).hex()
        input = {"task_id_commitment": task_id_commitment_hex}
        timestamp, signature = self.signer.sign(input)

        resp = await self.client.post(
            f"/v1/inference_tasks/{task_id_commitment_hex}/abort_reason",
            params={"abort_reason": abort_reason, "timestamp": timestamp, "signature": signature},
        )
        resp = _process_resp(resp, "reportTaskError")


    async def upload_task_result(self, task_id_commitment: bytes, file_paths: List[str], checkpoint_dir: Optional[str] = None):
        task_id_commitment_hex = HexBytes(task_id_commitment).hex()
        input = {"task_id_commitment": task_id_commitment_hex}
        timestamp, signature = self.signer.sign(input)

        with ExitStack() as stack:
            files = []
            for file_path in file_paths:
                filename = os.path.basename(file_path)
                file_obj = stack.enter_context(open(file_path, "rb"))
                files.append(("files", (filename, file_obj)))

            if checkpoint_dir is not None:
                tmp_dir = stack.enter_context(tempfile.TemporaryDirectory())
                checkpoint_file = os.path.join(tmp_dir, "checkpoint.zip")
                await to_thread.run_sync(shutil.make_archive, checkpoint_file[:-4], "zip", checkpoint_dir)
                filename = os.path.basename(checkpoint_file)
                file_obj = stack.enter_context(open(checkpoint_file, "rb"))
                files.append(("checkpoint", (filename, file_obj)))

            # disable timeout because there may be many images or image size may be very large
            resp = await self.client.post(
                f"/v1/inference_tasks/{task_id_commitment_hex}/results",
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
        task_id_commitment_hex = HexBytes(task_id_commitment).hex()
        input = {"task_id_commitment": task_id_commitment_hex, "index": str(index)}
        timestamp, signature = self.signer.sign(input)

        async_dst = wrap_file(dst)

        async with self.client.stream(
            "GET",
            f"/v1/inference_tasks/{task_id_commitment_hex}/results/{index}",
            params={"timestamp": timestamp, "signature": signature},
        ) as resp:
            resp = _process_resp(resp, "getTask")
            async for chunk in resp.aiter_bytes():
                await async_dst.write(chunk)

    async def get_result_checkpoint(self, task_id_commitment: bytes, result_checkpoint_dir: str):
        task_id_commitment_hex = HexBytes(task_id_commitment).hex()
        input = {"task_id_commitment": task_id_commitment_hex}
        timestamp, signature = self.signer.sign(input)

        with tempfile.TemporaryDirectory() as tmp_dir:
            checkpoint_file = os.path.join(tmp_dir, "checkpoint.zip")
            async with await open_file(checkpoint_file, mode="wb") as f:
                resp = await self.client.get(
                    f"/v1/inference_tasks/{task_id_commitment_hex}/results/checkpoint",
                    params={"timestamp": timestamp, "signature": signature},
                )
                resp = _process_resp(resp, "getResultCheckpoint")
                async for chunk in resp.aiter_bytes(4096):
                    await f.write(chunk)

            await to_thread.run_sync(
                shutil.unpack_archive, checkpoint_file, result_checkpoint_dir
            )

    """ auxiliary """

    async def now(self) -> int:
        resp = await self.client.get("/v1/now")
        resp = _process_resp(resp, "now")
        content = resp.json()
        data = content["data"]
        now = data["now"]
        return now

    async def close(self):
        await self.client.aclose()
    
    """ node related """

    async def node_get_node_info(self) -> NodeInfo:
        resp = await self.client.get(
            f"/v1/node/{self.node_address}",
            params={},
        )
        resp = _process_resp(resp, "nodeGetNodeInfo")
        content = resp.json()
        data = content["data"]
        return NodeInfo.model_validate(data)
    
    async def node_get_node_status(self) -> ChainNodeStatus:
        node_info = await self.node_get_node_info()
        return node_info.status
    
    async def node_join(self, gpu_name: str, gpu_vram: int, model_ids: List[str], version: str):
        input = {"gpu_name": gpu_name, "gpu_vram": gpu_vram, "model_ids": model_ids, "version": version}
        timestamp, signature = self.signer.sign(input)
        resp = await self.client.post(
            f"/v1/node/{self.node_address}/join",
            params={"gpu_name": gpu_name, "gpu_vram": gpu_vram, "model_ids": model_ids, "version": version, "timestamp": timestamp, "signature": signature},
        )
        resp = _process_resp(resp, "nodeJoin")
    
    async def node_report_model_downloaded(self, model_id: str):
        input = {"model_id": model_id}
        timestamp, signature = self.signer.sign(input)
        resp = await self.client.post(
            f"/v1/node/{self.node_address}/model",
            params={"model_id": model_id, "timestamp": timestamp, "signature": signature},
        )
        resp = _process_resp(resp, "nodeReportModelDownload")
    
    async def node_pause(self):
        input = {}
        timestamp, signature = self.signer.sign(input)
        resp = await self.client.post(
            f"/v1/node/{self.node_address}/pause",
            params={"timestamp": timestamp, "signature": signature},
        )
        resp = _process_resp(resp, "nodePause")
    
    async def node_quit(self):
        input = {}
        timestamp, signature = self.signer.sign(input)
        resp = await self.client.post(
            f"/v1/node/{self.node_address}/quit",
            params={"timestamp": timestamp, "signature": signature},
        )
        resp = _process_resp(resp, "nodeQuit")
    
    async def node_resume(self):
        input = {}
        timestamp, signature = self.signer.sign(input)
        resp = await self.client.post(
            f"/v1/node/{self.node_address}/resume",
            params={"timestamp": timestamp, "signature": signature},
        )
        resp = _process_resp(resp, "nodeResume")
    
    async def node_get_current_task(self) -> str:
        resp = await self.client.get(
            f"/v1/node/{self.node_address}/task",
            params={},
        )
        resp = _process_resp(resp, "getCurrentTask")
        content = resp.json()
        task_id_commitment = content["data"]
        return task_id_commitment
    
    async def node_update_version(self, version: str):
        input = {"version": version}
        timestamp, signature = self.signer.sign(input)
        resp = await self.client.post(
            f"/v1/node/{self.node_address}/version",
            params={"version": version, "timestamp": timestamp, "signature": signature},
        )
        resp = _process_resp(resp, "nodeUpdateNodeVersion")

    """ balance related """

    async def get_balance(self) -> int:
        resp = await self.client.get(
            f"/v1/balance/{self.node_address}",
            params={},
        )
        resp = _process_resp(resp, "getBalance")
        content = resp.json()
        balance = content["data"]
        return balance
    
    async def transfer(self, amount: int, to_addr: str):
        input = {"value": amount, "to": to_addr}
        timestamp, signature = self.signer.sign(input)
        resp = await self.client.post(
            f"/v1/balance/{self.node_address}/transfer",
            params={"value": amount, "to": to_addr, "timestamp": timestamp, "signature": signature},
        )
        resp = _process_resp(resp, "transfer")