from typing import TypedDict

class ModelConfig(TypedDict):
    id: str


class ProxyConfig(TypedDict, total=False):
    host: str
    port: int
    username: str
    password: str

