from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Literal, Optional, Tuple, Type

import yaml
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_settings import (BaseSettings, PydanticBaseSettingsSource,
                               SettingsConfigDict)


class YamlSettingsConfigDict(SettingsConfigDict):
    yaml_file: str | None


class YamlConfigSettingsSource(PydanticBaseSettingsSource):
    """
    A simple settings source class that loads variables from a YAML file

    Note: slightly adapted version of JsonConfigSettingsSource from docs.
    """

    _yaml_data: Dict[str, Any] | None = None

    # def __init__(self, settings_cls: type[BaseSettings]):
    #     super().__init__(settings_cls)

    @property
    def yaml_data(self) -> Dict[str, Any]:
        if self._yaml_data is None:
            yaml_file = self.config.get("yaml_file")
            if yaml_file is not None and os.path.exists(yaml_file):
                with open(yaml_file, mode="r", encoding="utf-8") as f:
                    self._yaml_data = yaml.safe_load(f)
            else:
                self._yaml_data = {}
        return self._yaml_data

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> Tuple[Any, str, bool]:
        field_value = self.yaml_data.get(field_name)
        return field_value, field_name, False

    def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool
    ) -> Any:
        return value

    def __call__(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}

        for field_name, field in self.settings_cls.model_fields.items():
            field_value, field_key, value_is_complex = self.get_field_value(
                field, field_name
            )
            field_value = self.prepare_field_value(
                field_name, field, field_value, value_is_complex
            )
            if field_value is not None:
                d[field_key] = field_value

        return d


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
    inference_logs_dir: str
    result_url: str

    preloaded_models: Optional[PreloadedModelsConfig] = None

    proxy: Optional[ProxyConfig] = None


class ModelConfig(BaseModel):
    id: str


class PreloadedModelsConfig(BaseModel):
    base: Optional[List[ModelConfig]] = None
    controlnet: Optional[List[ModelConfig]] = None
    vae: Optional[List[ModelConfig]] = None


class ProxyConfig(BaseModel):
    host: str = ""
    port: int = 8080
    username: str = ""
    password: str = ""


class Config(BaseSettings):
    log: LogConfig

    celery: CeleryConfig

    task: TaskConfig

    model_config = YamlSettingsConfigDict(
        env_nested_delimiter="__",
        yaml_file=os.getenv("CRYNUX_WORKER_CONFIG", "config/worker_config.yaml"),
        env_file=".env",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            YamlConfigSettingsSource(settings_cls),
            env_settings,
            dotenv_settings,
            file_secret_settings,
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

def set_env(
    hf_cache_dir: str,
    external_cache_dir: str,
    base_models: List[ModelConfig] | None = None,
    controlnet_models: List[ModelConfig] | None = None,
    vae_models: List[ModelConfig] | None = None,
    proxy: ProxyConfig | None = None
):
    envs = os.environ.copy()
    envs["data_dir__models__huggingface"] = os.path.abspath(hf_cache_dir)
    envs["data_dir__models__external"] = os.path.abspath(external_cache_dir)
    if base_models is not None:
        envs["preloaded_models__base"] = json.dumps(base_models)
    if controlnet_models is not None:
        envs["preloaded_models__controlnet"] = json.dumps(controlnet_models)
    if vae_models is not None:
        envs["preloaded_models__vae"] = json.dumps(vae_models)
    if proxy is not None:
        envs["proxy"] = json.dumps(proxy)
    return envs
