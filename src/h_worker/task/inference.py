import os
import random
import subprocess
from mimetypes import guess_extension, guess_type
from typing import Dict, Optional

import httpx

from h_worker import models
from h_worker.celery import celery
from h_worker.config import get_config

from .utils import get_image_hash

http_client = httpx.Client()


@celery.task(name="sd_lora_inference", track_started=True)
def sd_lora_inference(
    task_id: int,
    prompts: str,
    base_model: str,
    lora_model: str,
    task_config: Optional[models.TaskConfig] = None,
    pose: Optional[models.PoseConfig] = None,
):
    config = get_config()
    base_model_path = os.path.join(
        config.task.pretrained_models_dir, base_model, f"{base_model}.ckpt"
    )
    if not os.path.exists(base_model_path):
        raise ValueError("base model not found")

    lora_model_path = os.path.join(
        config.task.data_dir, "model", lora_model, "character.safetensors"
    )
    if not os.path.exists(lora_model_path):
        raise ValueError("lora model not found")

    image_dir = os.path.join(config.task.data_dir, "image", str(task_id))
    if not os.path.exists(image_dir):
        os.makedirs(image_dir, exist_ok=True)

    pose_file = ""
    pose_dir = os.path.join(config.task.data_dir, "pose", str(task_id))
    if not os.path.exists(pose_dir):
        os.makedirs(pose_dir, exist_ok=True)

    if pose is not None:
        if pose["data_url"] != "":
            data_url = pose["data_url"]
            file_type = guess_type(url=data_url)[0]
            file_ext = ".png"
            if file_type is not None:
                _file_ext = guess_extension(file_type, strict=False)
                if _file_ext is not None:
                    file_ext = _file_ext

            pose_file = os.path.join(pose_dir, "pose" + file_ext)
            with http_client.stream("GET", data_url) as resp:
                resp.raise_for_status()
                with open(pose_file, "wb") as dst:
                    for data in resp.iter_bytes():
                        dst.write(data)

    log_file = os.path.join(config.task.inference_logs_dir, f"{task_id}.log")

    envs: Dict[str, str] = {
        "PRETRAINED_MODEL": base_model_path,
        "MODEL_FILE": lora_model_path,
        "OUTPUT_DIR": image_dir,
        "PROMPTS": prompts,
    }
    if task_config is not None:
        envs.update(
            {
                "STEPS": str(task_config["steps"]),
                "MODEL_WEIGHT": str(task_config["lora_weight"]),
                "IMAGE_WIDTH": str(task_config["image_width"]),
                "IMAGE_HEIGHT": str(task_config["image_height"]),
                "NUM_IMAGES": str(task_config["num_images"]),
            }
        )

        seed = task_config["seed"]
        if seed == 0:
            seed = random.randint(10000000, 99999999)
        envs["SEED"] = str(seed)

    if pose is not None and pose_file != "":
        openpose_model_file = os.path.join(
            config.task.controlnet_models_dir, "control_v11p_sd15_openpose.pth"
        )

        if os.path.exists(openpose_model_file):
            envs.update(
                {
                    "POSE_IMAGE": pose_file,
                    "POSE_PREPROCESS": "1" if pose["preprocess"] else "0",
                    "CONTROLNET_MODEL": openpose_model_file,
                }
            )

    cwd = "/app/lora-scripts"
    if not os.path.exists(cwd):
        raise ValueError(f"Cwd {cwd} not exists")

    with open(log_file, mode="w", encoding="utf-8") as log_file:
        subprocess.run(
            "inference.sh",
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd="/app/lora-scripts",
            env=envs,
            check=True,
            encoding="utf-8",
        )

    hashes = []
    files = []
    image_files = sorted(os.listdir(image_dir))
    for image_file in image_files:
        image_path = os.path.join(image_dir, image_file)
        hashes.append(get_image_hash(image_path))
        files.append(("files", (image_file, open(image_path, "rb"), "image/png")))

    resp = http_client.post(
        config.task.result_api, files=files, data={"hashes": hashes}
    )
    resp.raise_for_status()
