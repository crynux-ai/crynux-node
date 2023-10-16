from sd_task.prefetch import prefetch_models
from huggingface_hub import snapshot_download


if __name__ == "__main__":
    prefetch_models()
    snapshot_download(
        "openai/clip-vit-large-patch14",
        cache_dir="{cache_dir}",
        resume_download=True,
        local_files_only=False,
        allow_patterns=["*.json", "*.txt", "model.safetensors"]
    )
