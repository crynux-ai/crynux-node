from typing import Optional

from .abc import Relay
from .exceptions import RelayError
from .mock_impl import MockRelay
from .web_impl import WebRelay

__all__ = ["Relay", "RelayError", "get_relay", "set_relay", "WebRelay", "MockRelay"]


_default_relay: Optional[Relay] = None


def get_relay() -> Relay:
    assert _default_relay is not None, "Relay has not been set."

    return _default_relay


def set_relay(relay: Relay):
    global _default_relay

    _default_relay = relay
