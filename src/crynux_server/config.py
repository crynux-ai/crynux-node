from __future__ import annotations

import functools
import os
from typing import Any, Dict, List, Literal, Tuple, Type, TypedDict, Optional

import yaml
from anyio import Condition, to_thread
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_settings import (BaseSettings, PydanticBaseSettingsSource,
                               SettingsConfigDict)
from web3 import Web3
from web3.types import Wei

__all__ = [
    "Config",
    "get_config",
    "set_config",
    "dump_config",
    "wait_privkey",
    "set_privkey",
    "get_privkey",
    "TxOption",
    "get_default_tx_option",
]


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


class LogConfig(BaseModel):
    dir: str
    level: LogLevel


class Contract(BaseModel):
    node: str
    task: str
    qos: Optional[str] = None
    task_queue: Optional[str] = None
    netstats: Optional[str] = None


class Ethereum(BaseModel):
    provider: str
    privkey: str = ""

    chain_id: Optional[int] = None
    gas: Optional[int] = None
    gas_price: Optional[int] = None
    max_fee_per_gas: Optional[int] = None
    max_priority_fee_per_gas: Optional[int] = None

    contract: Contract


class CeleryConfig(BaseModel):
    broker: str
    backend: str


class TaskConfig(BaseModel):
    output_dir: str
    hf_cache_dir: str
    external_cache_dir: str
    script_dir: str
    inference_logs_dir: str

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

    ethereum: Ethereum

    db: str
    task_dir: str
    relay_url: str

    celery: Optional[CeleryConfig] = None

    distributed: bool = False
    task_config: Optional[TaskConfig] = None

    server_host: str = "0.0.0.0"
    server_port: int = 7412
    web_dist: str = ""
    headless: bool = False

    resource_dir: str = ""

    last_result: Optional[str] = None

    model_config = YamlSettingsConfigDict(
        env_nested_delimiter="__",
        yaml_file=os.getenv("CRYNUX_SERVER_CONFIG", "config/server_config.yaml"),
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


def dump_config(config: Config):
    config_file: Optional[str] = config.model_config.get("yaml_file")
    assert config_file is not None
    with open(config_file, mode="w", encoding="utf-8") as f:
        yaml.safe_dump(config.model_dump(), f)


_condition: Optional[Condition] = None


def _get_condition() -> Condition:
    global _condition

    if _condition is None:
        _condition = Condition()

    return _condition


async def wait_privkey() -> str:
    config = get_config()
    condition = _get_condition()
    async with condition:
        while len(config.ethereum.privkey) == 0:
            await condition.wait()
        return config.ethereum.privkey


async def set_privkey(privkey: str):
    config = get_config()
    condition = _get_condition()
    async with condition:
        config.ethereum.privkey = privkey
        condition.notify(1)

    await to_thread.run_sync(functools.partial(dump_config, config=config))


def get_privkey() -> str:
    config = get_config()
    return config.ethereum.privkey


class TxOption(TypedDict, total=False):
    chainId: int
    gas: int
    gasPrice: Wei
    maxFeePerGas: Wei
    maxPriorityFeePerGas: Wei


def get_default_tx_option() -> TxOption:
    config = get_config()
    res: TxOption = {}

    if config.ethereum.chain_id is not None:
        res["chainId"] = config.ethereum.chain_id
    if config.ethereum.gas is not None:
        res["gas"] = config.ethereum.gas
    if config.ethereum.gas_price is not None:
        res["gasPrice"] = Web3.to_wei(config.ethereum.gas_price, "wei")
    if config.ethereum.max_fee_per_gas is not None:
        res["maxFeePerGas"] = Web3.to_wei(config.ethereum.max_fee_per_gas, "wei")
    if config.ethereum.max_priority_fee_per_gas is not None:
        res["maxPriorityFeePerGas"] = Web3.to_wei(
            config.ethereum.max_priority_fee_per_gas, "wei"
        )
    return res
