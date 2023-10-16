import os
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
    output_dir: str
    hf_cache_dir: str
    external_cache_dir: str
    script_dir: str
    result_url: str


class Config(YamlBaseSettings):
    log: LogConfig

    celery: CeleryConfig

    task: TaskConfig

    model_config = SettingsConfigDict(
        yaml_file=os.getenv("H_SERVER_CONFIG", "config/worker_config.yaml")  # type: ignore
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
