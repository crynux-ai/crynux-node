from __future__ import annotations

import os
from functools import partial
from typing import Any, Dict, List, Literal, Tuple, Type, TypedDict, Optional

import yaml
from anyio import Condition, to_thread
from pydantic import BaseModel, computed_field, Field
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from web3 import Web3
from web3.types import Wei

__all__ = [
    "Config",
    "get_config",
    "set_config",
    "wait_privkey",
    "set_privkey",
    "get_privkey",
    "TxOption",
    "get_default_tx_option",
]


_data_dir: str = ""
_config_dir: str = "config"


def config_file_path():
    return os.path.join(_data_dir, _config_dir, "config.yml")


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
            yaml_file = config_file_path()
            if yaml_file is not None and os.path.exists(yaml_file):
                with open(yaml_file, mode="r", encoding="utf-8") as f:
                    self._yaml_data = yaml.safe_load(f)
            else:
                self._yaml_data = {}
        return self._yaml_data  # type: ignore

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
DBDriver = Literal["sqlite"]


def set_data_dir(dirname: str):
    global _data_dir

    _data_dir = dirname


class LogConfig(BaseModel):
    m_dir: str = Field(alias="dir")
    level: LogLevel
    filename: str = "crynux-server.log"

    @computed_field
    @property
    def dir(self) -> str:
        return os.path.abspath(os.path.join(_data_dir, self.m_dir))


class DBConfig(BaseModel):
    driver: DBDriver
    m_filename: str = Field(alias="filename")

    @computed_field
    @property
    def filename(self) -> str:
        return os.path.abspath(os.path.join(_data_dir, self.m_filename))

    @computed_field
    @property
    def connection(self) -> str:
        if self.driver == "sqlite":
            return f"sqlite+aiosqlite:///{self.filename}"
        else:
            raise ValueError(f"unsupported db driver {self.driver}")


class Contract(BaseModel):
    node: str
    task: str
    qos: Optional[str] = None
    task_queue: Optional[str] = None
    netstats: Optional[str] = None


class Ethereum(BaseModel):
    provider: str

    chain_id: Optional[int] = None
    gas: Optional[int] = None
    gas_price: Optional[int] = None
    max_fee_per_gas: Optional[int] = None
    max_priority_fee_per_gas: Optional[int] = None

    contract: Contract

    _privkey_file: str = "private_key.txt"
    _privkey: str = ""

    @property
    def privkey(self) -> str:
        if len(self._privkey) == 0:
            privkey_file = os.path.join(_data_dir, _config_dir, self._privkey_file)
            if os.path.exists(privkey_file):
                with open(privkey_file, mode="r", encoding="utf-8") as f:
                    self._privkey = f.read().strip()
        return self._privkey

    @privkey.setter
    def privkey(self, privkey: str):
        self._privkey = privkey

    def dump_privkey(self, privkey: str):
        privkey_file = os.path.join(_data_dir, _config_dir, self._privkey_file)
        with open(privkey_file, mode="w", encoding="utf-8") as f:
            f.write(privkey)


class TaskConfig(BaseModel):
    _hf_cache_dir: str = "data/huggingface"
    _external_cache_dir: str = "data/external"
    _script_dir: str = "worker"
    _output_dir: str = "data/results"

    worker_patch_url: str

    preloaded_models: Optional[PreloadedModelsConfig] = None

    proxy: Optional[ProxyConfig] = None

    @computed_field
    @property
    def hf_cache_dir(self) -> str:
        return os.path.abspath(os.path.join(_data_dir, self._hf_cache_dir))

    @computed_field
    @property
    def external_cache_dir(self) -> str:
        return os.path.abspath(os.path.join(_data_dir, self._external_cache_dir))

    @computed_field
    @property
    def script_dir(self) -> str:
        return os.path.abspath(os.path.join(_data_dir, self._script_dir))

    @computed_field
    @property
    def output_dir(self) -> str:
        return os.path.abspath(os.path.join(_data_dir, self._output_dir))


class ModelConfig(BaseModel):
    id: str
    variant: str | None = "fp16"


class PreloadedModelsConfig(BaseModel):
    sd_base: Optional[List[ModelConfig]] = None
    gpt_base: Optional[List[ModelConfig]] = None
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

    db: DBConfig
    relay_url: str

    task_config: TaskConfig

    server_host: str = "0.0.0.0"
    server_port: int = 7412
    web_dist: str = ""

    resource_dir: str = ""

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
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

    await to_thread.run_sync(partial(config.ethereum.dump_privkey, privkey=privkey))


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
