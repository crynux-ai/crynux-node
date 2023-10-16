from h_worker.prefetch import prefetch


def test_prefetch():
    prefetch(
        "models/huggingface",
        "models/external",
        "stable-diffusion-task",
    )
