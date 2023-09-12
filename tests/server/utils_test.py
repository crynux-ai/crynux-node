from h_server import utils


async def test_gpu_info():
    gpu_info = await utils.get_gpu_info()
    assert len(gpu_info.model) > 0
    assert gpu_info.vram_total > 0
    assert gpu_info.vram_used > 0


async def test_cpu_info():
    cpu_info = await utils.get_cpu_info()
    assert cpu_info.frequency > 0
    assert cpu_info.num_cores > 0
    assert cpu_info.usage > 0


async def test_memory_info():
    memory_info = await utils.get_memory_info()
    assert memory_info.available > 0
    assert memory_info.total > 0
    assert memory_info.available < memory_info.total


async def test_disk_info():
    disk_info = utils.get_disk_info("build/data/pretrained-models", "build/data/workspace/model", "build/data/inference-logs")
    assert disk_info.base_models > 0
    assert disk_info.lora_models > 0
    assert disk_info.logs > 0