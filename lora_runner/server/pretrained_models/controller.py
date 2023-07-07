from lora_runner.server.response import response_data
from lora_runner.config import config
import os


def list_pretrained_models():
    pt_models_dir = config['pretrained_models_dir']
    model_names = []

    with os.scandir(pt_models_dir) as entries:
        for entry in entries:
            if entry.is_dir():
                model_names.append(entry.name)

    return response_data(model_names)
