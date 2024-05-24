import json
import os
from contextlib import ExitStack
from typing import BinaryIO, List

import httpx
from anyio import wrap_file

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

    async def create_task(self, task_id: int, task_args: str) -> RelayTask:
        input = {"task_id": task_id, "task_args": task_args}
        timestamp, signature = self.signer.sign(input)
        input.update({"timestamp": timestamp, "signature": signature})

        resp = await self.client.post("/v1/inference_tasks", json=input)
        resp = _process_resp(resp, "createTask")
        content = resp.json()
        data = content["data"]
        return RelayTask.model_validate(data)

    async def get_task(self, task_id: int) -> RelayTask:
        input = {"task_id": task_id}
        timestamp, signature = self.signer.sign(input)

        resp = await self.client.get(
            f"/v1/inference_tasks/{task_id}",
            params={"timestamp": timestamp, "signature": signature},
        )
        resp = _process_resp(resp, "getTask")
        content = resp.json()
        data = content["data"]
        return RelayTask.model_validate(data)

    async def upload_task_result(self, task_id: int, file_paths: List[str]):
        input = {"task_id": task_id}
        timestamp, signature = self.signer.sign(input)

        with ExitStack() as stack:
            files = []
            for file_path in file_paths:
                filename = os.path.basename(file_path)
                file_obj = stack.enter_context(open(file_path, "rb"))
                files.append(("images", (filename, file_obj)))

            # disable timeout because there may be many images or image size may be very large
            resp = await self.client.post(
                f"/v1/inference_tasks/{task_id}/results",
                data={"timestamp": timestamp, "signature": signature},
                files=files,
                timeout=None
            )
            resp = _process_resp(resp, "uploadTaskResult")
            content = resp.json()
            message = content["message"]
            if message != "success":
                raise RelayError(resp.status_code, "uploadTaskResult", message)

    async def get_result(self, task_id: int, index: int, dst: BinaryIO):
        input = {"task_id": task_id, "image_num": str(index)}
        timestamp, signature = self.signer.sign(input)

        async_dst = wrap_file(dst)

        async with self.client.stream(
            "GET",
            f"/v1/inference_tasks/{task_id}/results/{index}",
            params={"timestamp": timestamp, "signature": signature},
        ) as resp:
            resp = _process_resp(resp, "getTask")
            async for chunk in resp.aiter_bytes():
                await async_dst.write(chunk)

    async def close(self):
        await self.client.aclose()
