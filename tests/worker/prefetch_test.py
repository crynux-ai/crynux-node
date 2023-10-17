from h_worker.prefetch import prefetch


def test_prefetch():
    prefetch(
        "build/data/huggingface",
        "build/data/external",
        "stable-diffusion-task",
    )
