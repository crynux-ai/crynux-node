import torch

gpu_info = {
    "cuda_available": torch.cuda.is_available(),
    "device_count": torch.cuda.device_count(),
    "current_device": torch.cuda.current_device()
}

if gpu_info["cuda_available"]:
    gpu_info["device_name"] = torch.cuda.get_device_name(gpu_info["current_device"])

print(gpu_info)
