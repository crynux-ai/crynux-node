import logging
import os
import subprocess

import httpx

_logger = logging.getLogger(__name__)

base_model_urls = {
    "stable-diffusion-v1-5-pruned": "https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned.ckpt",
    "stable-diffusion-2-1": "https://huggingface.co/stabilityai/stable-diffusion-2-1/resolve/main/v2-1_768-nonema-pruned.ckpt",
}


def _prefetch_base_model(
    client: httpx.Client, pretrained_models_dir: str, base_model: str
):
    base_model_path = os.path.join(
        pretrained_models_dir, base_model, f"{base_model}.ckpt"
    )
    if not os.path.exists(base_model_path):
        _logger.info(f"Downloading base model {base_model}")
        model_dir = os.path.dirname(base_model_path)
        if not os.path.exists(model_dir):
            os.makedirs(model_dir, exist_ok=True)

        url = base_model_urls[base_model]
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(base_model_path, mode="wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
        _logger.info(f"Base model {base_model} download finished")


def _prefetch_huggingface(huggingface_cache_dir: str, script_dir: str):
    exe = "python"
    worker_venv = os.path.abspath(os.path.join(script_dir, "venv"))
    if os.path.exists(worker_venv):
        exe = os.path.join(worker_venv, "bin", "python")

    args = [
        exe,
        "-c",
        "from transformers import CLIPTextModel, CLIPTokenizer;"
        "CLIPTokenizer.from_pretrained('openai/clip-vit-large-patch14');"
        "CLIPTextModel.from_pretrained('openai/clip-vit-large-patch14')",
    ]

    envs = os.environ.copy()
    envs["HF_HOME"] = os.path.abspath(huggingface_cache_dir)
    subprocess.check_call(args, env=envs, cwd=script_dir)
    _logger.info(f"Model openai/clip-vit-large-patch14 download finished")


def prefetch(pretrained_models_dir: str, huggingface_cache_dir: str, script_dir: str):
    if not os.path.exists(pretrained_models_dir):
        os.makedirs(pretrained_models_dir, exist_ok=True)

    if not os.path.exists(huggingface_cache_dir):
        os.makedirs(huggingface_cache_dir, exist_ok=True)

    with httpx.Client() as client:
        for base_model in base_model_urls:
            _prefetch_base_model(client, pretrained_models_dir, base_model)

    _prefetch_huggingface(huggingface_cache_dir, script_dir)