import json
import os.path
from typing import List, Optional

import httpx

from h_server.models import RelayTask

from .exceptions import RelayError
from .sign import Signer

__all__ = ["Relay", "RelayError", "get_relay", "set_relay"]


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
        raise RelayError(resp.status_code, method, message)


class Relay(object):
    def __init__(self, base_url: str, privkey: str) -> None:
        self.client = httpx.AsyncClient(base_url=base_url)
        self.signer = Signer(privkey=privkey)

    async def get_task(self, task_id: int) -> RelayTask:
        input = {"task_id": task_id}
        timestamp, signature = self.signer.sign(input)

        resp = await self.client.get(
            f"/{task_id}", params={"timestamp": timestamp, "signature": signature}
        )
        resp = _process_resp(resp, "getTask")
        content = resp.json()
        data = content["data"]
        return RelayTask.model_validate(data)

    async def upload_task_result(self, task_id: int, file_paths: List[str]):
        input = {"task_id": task_id}
        timestamp, signature = self.signer.sign(input)

        files = []
        for file_path in file_paths:
            filename = os.path.basename(file_path)
            files.append(("images", (filename, open(file_path, "rb"), "image/png")))

        resp = await self.client.post(
            f"/{task_id}/results",
            data={"timestamp": timestamp, "signature": signature},
            files=files,
        )
        resp = _process_resp(resp, "uploadTaskResult")
        content = resp.json()
        message = content["message"]
        if message != "success":
            raise RelayError(resp.status_code, "uploadTaskResult", message)

    async def close(self):
        await self.client.aclose()


_default_relay: Optional[Relay] = None


def get_relay() -> Relay:
    assert _default_relay is not None, "Relay has not been set."

    return _default_relay


def set_relay(relay: Relay):
    global _default_relay

    _default_relay = relay
