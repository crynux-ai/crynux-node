from typing import Literal, Optional

from pydantic import BaseModel
from pydantic_settings import SettingsConfigDict
from pydantic_settings_yaml import YamlBaseSettings

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "FATAL", "CRITICAL"]


class CeleryConfig(BaseModel):
    broker: str
    backend: str


class LogConfig(BaseModel):
    dir: str
    level: LogLevel


class TaskConfig(BaseModel):
    data_dir: str
    pretrained_models_dir: str
    controlnet_models_dir: str
    training_logs_dir: str
    inference_logs_dir: str
    cwd: str
    result_api: str


class Config(YamlBaseSettings):
    log: LogConfig

    celery: CeleryConfig

    task: TaskConfig

    model_config = SettingsConfigDict(
        yaml_file=os.getenv("H_SERVER_CONFIG", "config/config.yaml")  # type: ignore
    )


_config: Optional[Config] = None


def get_config():
    global _config

    if _config is None:
        _config = Config()  # type: ignore

    return _config


def set_config(config: Config):
    global _config
    _config = config
