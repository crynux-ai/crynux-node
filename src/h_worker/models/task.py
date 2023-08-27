from typing import TypedDict


class TaskConfig(TypedDict):
    image_width: int
    image_height: int
    lora_weight: float
    num_images: int
    seed: int
    steps: int


class PoseConfig(TypedDict):
    data_url: str
    pose_weight: float
    preprocess: bool
