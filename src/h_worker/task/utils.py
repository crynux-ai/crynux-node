import hashlib
import os.path
from mimetypes import guess_extension, guess_type
from typing import List
from urllib.parse import urlparse

import httpx

import imhash

from .error import TaskError

http_client = httpx.Client()


def get_image_hash(filename: str) -> str:
    return imhash.getPHash(filename)  # type: ignore


def is_valid_url(url: str) -> bool:
    try:
        res = urlparse(url)
        return all([res.scheme, res.netloc])
    except ValueError:
        return False


def get_lora_model(lora_model: str, data_dir: str) -> str:
    lora_model_id = hashlib.md5(lora_model.encode("utf-8")).hexdigest()
    lora_model_dir = os.path.abspath(os.path.join(data_dir, "model", lora_model_id))
    if not os.path.exists(lora_model_dir):
        os.makedirs(lora_model_dir, exist_ok=True)

    lora_model_path = os.path.join(lora_model_dir, "lora.safetensors")
    if not is_valid_url(lora_model):
        raise TaskError("lora model", f"{lora_model} is not a valid url")
    if not os.path.exists(lora_model_path):
        try:
            with http_client.stream("GET", lora_model, follow_redirects=True) as resp:
                resp.raise_for_status()
                with open(lora_model_path, mode="wb") as dst:
                    for data in resp.iter_bytes():
                        dst.write(data)
        except httpx.HTTPStatusError as e:
            raise TaskError("lora model", str(e))

    return lora_model_path


def get_pose_file(data_dir: str, task_id: int, pose_url: str) -> str:
    pose_dir = os.path.abspath(os.path.join(data_dir, "pose", str(task_id)))
    if not os.path.exists(pose_dir):
        os.makedirs(pose_dir, exist_ok=True)

    file_type = guess_type(url=pose_url)[0]
    file_ext = ".png"
    if file_type is not None:
        _file_ext = guess_extension(file_type, strict=False)
        if _file_ext is not None:
            file_ext = _file_ext

    pose_file = os.path.join(pose_dir, "pose" + file_ext)
    if not is_valid_url(pose_url):
        raise TaskError("pose", f"{pose_url} is not a valid url")
    try:
        with http_client.stream("GET", pose_url) as resp:
            resp.raise_for_status()
            with open(pose_file, "wb") as dst:
                for data in resp.iter_bytes():
                    dst.write(data)
    except httpx.HTTPStatusError as e:
        raise TaskError("pose", str(e))

    return pose_file


def upload_result(result_url: str, images: List[str]):
    hashes = []
    files = []
    for image in images:
        image_name = os.path.basename(image)
        hashes.append(get_image_hash(image))
        files.append(("files", (image_name, open(image, "rb"), "image/png")))

    resp = http_client.post(
        result_url,
        files=files,
        data={"hashes": hashes},
    )
    resp.raise_for_status()
