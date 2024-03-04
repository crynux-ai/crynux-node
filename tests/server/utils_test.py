from crynux_server import utils


async def test_gpu_info():
    gpu_info = await utils.get_gpu_info()
    assert len(gpu_info.model) > 0
    assert gpu_info.vram_total_mb > 0
    assert gpu_info.vram_used_mb > 0


async def test_cpu_info():
    cpu_info = await utils.get_cpu_info()
    if utils.get_os() == "Darwin":
        assert cpu_info.description
    elif utils.get_os() == "Linux":
        assert cpu_info.frequency_mhz > 0
    assert cpu_info.num_cores > 0
    assert cpu_info.usage > 0


async def test_memory_info():
    memory_info = await utils.get_memory_info()
    assert memory_info.available_mb > 0
    assert memory_info.total_mb > 0
    assert memory_info.available_mb < memory_info.total_mb


async def test_disk_info():
    disk_info = await utils.get_disk_info("build/data/pretrained-models", "build/data/workspace/model", "logs", "build/data/inference-logs")
    assert disk_info.base_models >= 0
    assert disk_info.lora_models >= 0
    assert disk_info.logs >= 0