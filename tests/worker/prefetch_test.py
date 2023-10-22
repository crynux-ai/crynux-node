from h_worker.prefetch import prefetch


def test_prefetch():
    prefetch(
        "build/data/huggingface",
        "build/data/external",
        "stable-diffusion-task",
        base_models=[],
        controlnet_models=[],
        vae_models=[],
        proxy={"host": "192.168.224.1", "port": 10081}
    )
