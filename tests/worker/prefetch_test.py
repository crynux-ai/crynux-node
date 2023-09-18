from h_worker.prefetch import prefetch_huggingface, prefetch


def test_prefetch_huggingface():
    prefetch_huggingface(
        "remote-lora-scripts/huggingface",
        "remote-lora-scripts",
    )


def test_prefetch():
    prefetch(
        "build/data/pretrained-models",
        "remote-lora-scripts/huggingface",
        "remote-lora-scripts",
    )
