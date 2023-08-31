import os
from typing import Literal, Optional, TypedDict

from pydantic import BaseModel
from pydantic_settings import SettingsConfigDict
from pydantic_settings_yaml import YamlBaseSettings
from web3 import Web3
from web3.types import Wei

__all__ = ["Config", "get_config", "set_config", "TxOption", "get_default_tx_option"]

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "FATAL", "CRITICAL"]


class LogConfig(BaseModel):
    dir: str
    level: LogLevel


class Contract(BaseModel):
    token: str
    node: str
    task: str


class Ethereum(BaseModel):
    privkey: str
    provider: str

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
    data_dir: str
    pretrained_models_dir: str
    controlnet_models_dir: str
    training_logs_dir: str
    inference_logs_dir: str
    script_dir: str
    result_url: str


class Config(YamlBaseSettings):
    log: LogConfig

    ethereum: Ethereum

    db: str
    task_dir: str
    relay_url: str

    celery: Optional[CeleryConfig] = None

    distributed: bool = True
    task_config: Optional[TaskConfig] = None

    server_host: str = "0.0.0.0"
    server_port: int = 7412

    model_config = SettingsConfigDict(
        yaml_file=os.getenv("H_SERVER_CONFIG", "config/server_config.yaml")  # type: ignore
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
