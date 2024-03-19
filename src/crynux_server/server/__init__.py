from typing import Optional

from .app import Server

__all__ = ["Server", "get_server", "set_server"]

_server: Optional[Server] = None


def get_server() -> Server:
    assert _server is not None, "Server has not been set."

    return _server


def set_server(server: Server):
    global _server

    _server = server
