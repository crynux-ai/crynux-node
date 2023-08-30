import hashlib
import importlib
import os.path
import subprocess
from mimetypes import guess_extension, guess_type
from typing import List, TextIO

import httpx

http_client = httpx.Client()


def get_image_hash(filename: str) -> str:
    dirname = os.path.dirname(os.path.abspath(__file__))
    imhash = os.path.join(dirname, "imhash")
    res = subprocess.check_output([imhash, "-f", filename], encoding="utf-8")
    return res.strip()


def get_lora_model(lora_model: str, data_dir: str) -> str:
    lora_model_id = hashlib.md5(lora_model.encode("utf-8")).hexdigest()
    lora_model_dir = os.path.abspath(os.path.join(data_dir, "model", lora_model_id))
    if not os.path.exists(lora_model_dir):
        os.makedirs(lora_model_dir, exist_ok=True)

    lora_model_path = os.path.join(lora_model_dir, "lora.safetensors")
    if not os.path.exists(lora_model_path):
        with http_client.stream("GET", lora_model, follow_redirects=True) as resp:
            resp.raise_for_status()
            with open(lora_model_path, mode="wb") as dst:
                for data in resp.iter_bytes():
                    dst.write(data)

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
    with http_client.stream("GET", pose_url) as resp:
        resp.raise_for_status()
        with open(pose_file, "wb") as dst:
            for data in resp.iter_bytes():
                dst.write(data)

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


def print_gpu_info(log_file: TextIO):
    torch = importlib.import_module("torch")

    gpu_info = {
        "cuda_available": torch.cuda.is_available(),
        "device_count": torch.cuda.device_count(),
        "current_device": torch.cuda.current_device(),
    }

    if gpu_info["cuda_available"]:
        gpu_info["device_name"] = torch.cuda.get_device_name(gpu_info["current_device"])

    print(gpu_info, file=log_file)
