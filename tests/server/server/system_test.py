from fastapi.testclient import TestClient


async def test_system_api(client: TestClient):
    resp = client.get("/manager/v1/system")
    resp.raise_for_status()

    resp_data = resp.json()

    gpu_info = resp_data["gpu"]
    assert gpu_info["usage"] >= 0
    assert len(gpu_info["model"]) > 0
    assert gpu_info["vram_used_mb"] > 0
    assert gpu_info["vram_total_mb"] > 0

    cpu_info = resp_data["cpu"]
    assert cpu_info["usage"] > 0
    assert cpu_info["num_cores"] > 0
    assert cpu_info["frequency"] > 0

    memory_info = resp_data["memory"]
    assert memory_info["available_mb"] > 0
    assert memory_info["total_mb"] > 0

    disk_info = resp_data["disk"]
    assert disk_info["base_models"] >= 0
    assert disk_info["lora_models"] >= 0
    assert disk_info["logs"] >= 0
