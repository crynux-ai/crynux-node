from typing import Optional

from .abc import Faucet
from .mock_impl import MockFaucet
from .web_impl import WebFaucet

__all__ = ["Faucet", "MockFaucet", "WebFaucet", "get_faucet", "set_faucet"]


_default_faucet: Optional[Faucet] = None


def get_faucet() -> Faucet:
    assert _default_faucet is not None, "Fauce has not been set"

    return _default_faucet


def set_faucet(faucet: Faucet):
    global _default_faucet

    _default_faucet = faucet
