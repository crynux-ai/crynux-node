import os
import logging
import random
import shutil
import subprocess
from typing import Optional

from h_worker import models
from h_worker.config import get_config

from . import utils
from .error import TaskError

_logger = logging.getLogger(__name__)


def sd_lora_inference(
    task_id: int,
    prompts: str,
    base_model: str,
    lora_model: str,
    distributed: bool = True,
    local_config: Optional[models.LocalConfig] = None,
    task_config: Optional[models.TaskConfig] = None,
    pose: Optional[models.PoseConfig] = None,
):
    if local_config is None:
        config = get_config()
        local_config = models.LocalConfig(**config.task.model_dump())

    _logger.info(
        f"task id: {task_id},"
        f"prompts: {prompts},"
        f"base model: {base_model},"
        f"lora_model: {lora_model},"
        f"local config: {local_config},"
        f"task config: {task_config},"
        f"pose: {pose}"
    )

    # Check if venv exists. If it exits, use the venv interpreter; else use the current interpreter
    exe = "python"
    worker_venv = os.path.abspath(os.path.join(local_config["script_dir"], "venv"))
    if os.path.exists(worker_venv):
        exe = os.path.join(worker_venv, "bin", "python")

    args = [
        exe,
        os.path.abspath(os.path.join(local_config["script_dir"], "sd-scripts/gen_img_diffusers.py"))
    ]

    base_model_path = os.path.abspath(
        os.path.join(
            local_config["pretrained_models_dir"], base_model, f"{base_model}.ckpt"
        )
    )
    if not os.path.exists(base_model_path):
        raise TaskError("base model", f"base model '{base_model}' not found")

    lora_model_path = utils.get_lora_model(
        lora_model=lora_model, data_dir=local_config["data_dir"]
    )

    image_dir = os.path.abspath(
        os.path.join(local_config["data_dir"], "image", str(task_id))
    )
    if not os.path.exists(image_dir):
        os.makedirs(image_dir, exist_ok=True)

    if pose is not None and len(pose["data_url"]) > 0:
        pose_file = utils.get_pose_file(
            data_dir=local_config["data_dir"],
            task_id=task_id,
            pose_url=pose["data_url"],
        )
    else:
        pose_file = ""

    log_file = os.path.abspath(
        os.path.join(local_config["inference_logs_dir"], f"{task_id}.log")
    )

    args.extend(["--ckpt", base_model_path])
    args.extend(["--outdir", image_dir])
    args.extend(["--xformers"])
    args.extend(["--prompt", prompts])
    args.extend(["--sampler", "k_euler_a"])
    args.extend(["--network_module", "networks.lora"])
    args.extend(["--network_weights", lora_model_path])
    args.extend(["--max_embeddings_multiples", "3"])
    if task_config is not None:
        args.extend(["--steps", str(task_config["steps"])])
        args.extend(["--W", str(task_config["image_width"])])
        args.extend(["--H", str(task_config["image_height"])])
        args.extend(["--network_mul", str(task_config["lora_weight"] / 100)])
        args.extend(["--images_per_prompt", str(task_config["num_images"])])

        seed = task_config["seed"]
        if seed == 0:
            seed = random.randint(10000000, 99999999)
        args.extend(["--seed", str(seed)])

    if pose is not None and pose_file != "":
        openpose_model_file = os.path.abspath(
            os.path.join(
                local_config["controlnet_models_dir"], "control_v11p_sd15_openpose.pth"
            )
        )

        if os.path.exists(openpose_model_file):
            args.extend(["--control_net_models", openpose_model_file])
            args.extend(["--guide_image_path", pose_file])
            args.extend(["--control_net_weights", str(pose["pose_weight"] / 100)])
            if pose["preprocess"]:
                args.extend(["--control_net_preps", "canny_63_191"])
            else:
                args.extend(["--control_net_preps", "none"])

    envs = os.environ.copy()
    envs.update(
        {
            "HF_DATASETS_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HOME": "huggingface",
        }
    )

    with open(log_file, mode="w", encoding="utf-8") as log_file:
        subprocess.run(
            args,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=envs,
            check=True,
            encoding="utf-8",
            cwd=local_config["script_dir"],
        )
    _logger.info("Inference task success.")

    if distributed:
        image_files = sorted(os.listdir(image_dir))
        image_paths = [os.path.join(image_dir, file) for file in image_files]

        utils.upload_result(
            local_config["result_url"] + f"/v1/tasks/{task_id}/result", image_paths
        )
        _logger.info("Upload inference task result.")

def mock_lora_inference(
    task_id: int,
    prompts: str,
    base_model: str,
    lora_model: str,
    distributed: bool = True,
    local_config: Optional[models.LocalConfig] = None,
    task_config: Optional[models.TaskConfig] = None,
    pose: Optional[models.PoseConfig] = None,
):
    if local_config is None:
        config = get_config()
        local_config = models.LocalConfig(**config.task.model_dump())
    _logger.info(
        f"task id: {task_id},"
        f"prompts: {prompts},"
        f"base model: {base_model},"
        f"lora_model: {lora_model},"
        f"local config: {local_config},"
        f"task config: {task_config},"
        f"pose: {pose}"
    )

    image_dir = os.path.abspath(
        os.path.join(local_config["data_dir"], "image", str(task_id))
    )
    if not os.path.exists(image_dir):
        os.makedirs(image_dir, exist_ok=True)

    shutil.copyfile("test.png", os.path.join(image_dir, "test.png"))

    if distributed:
        utils.upload_result(
            local_config["result_url"] + f"/v1/tasks/{task_id}/result", ["test.png"]
        )
        _logger.info("Upload inference task result.")
