from typing import TypedDict


class LocalConfig(TypedDict):
    data_dir: str
    pretrained_models_dir: str
    controlnet_models_dir: str
    training_logs_dir: str
    inference_logs_dir: str
    script_dir: str
    result_url: str


class TaskConfig(TypedDict):
    image_width: int
    image_height: int
    lora_weight: int
    num_images: int
    seed: int
    steps: int


class PoseConfig(TypedDict):
    data_url: str
    pose_weight: int
    preprocess: bool
