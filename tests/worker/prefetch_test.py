from h_worker.prefetch import prefetch


def test_prefetch():
    prefetch(
        "build/data/huggingface",
        "build/data/external",
        "stable-diffusion-task",
        base_models=[{"id": "runwayml/stable-diffusion-v1-5"}],
        controlnet_models=[],
        vae_models=[],
    )
