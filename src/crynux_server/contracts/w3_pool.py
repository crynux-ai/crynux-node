import logging
import ssl
import warnings
from abc import ABC, abstractmethod
from collections import deque
from contextlib import asynccontextmanager
from enum import IntEnum
from typing import Awaitable, Callable, Optional, Dict, cast

import certifi
from aiohttp import ClientSession, ClientTimeout, TCPConnector
from anyio import Condition, Lock, move_on_after
from eth_account import Account
from eth_keys import keys
from eth_account.signers.local import LocalAccount
from eth_typing import ChecksumAddress
from web3 import AsyncHTTPProvider, AsyncWeb3, WebsocketProviderV2
from web3.middleware.signing import async_construct_sign_and_send_raw_middleware
from web3.providers.async_base import AsyncBaseProvider
from websockets import ConnectionClosed

_logger = logging.getLogger(__name__)


class ProviderType(IntEnum):
    HTTP = 0
    WS = 1
    Other = 2


_W3PoolCallback = Callable[[int], Awaitable[None]]


class W3Guard(ABC):
    def __init__(
        self,
        id: int,
        w3: AsyncWeb3,
        on_idle: _W3PoolCallback,
        on_close: _W3PoolCallback,
    ):
        self._id = id
        self._w3 = w3
        self._on_idle = on_idle
        self._on_close = on_close

    async def __aenter__(self) -> AsyncWeb3:
        return self._w3

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        with move_on_after(5, shield=True):
            if isinstance(exc_val, ConnectionClosed):
                await self.close()
                _logger.error(f"w3 guard {self._id} is closed due to ConnectionClosed")
                return True
            await self._on_idle(self._id)
            return False

    @abstractmethod
    async def close(self): ...


class HTTPW3Guard(W3Guard):
    def __init__(
        self,
        id: int,
        w3: AsyncWeb3,
        on_idle: Callable[[int], Awaitable[None]],
        on_close: Callable[[int], Awaitable[None]],
        session: ClientSession,
    ):
        super().__init__(id, w3, on_idle, on_close)

        self._session = session

    async def close(self) -> None:
        if not self._session.closed:
            with move_on_after(5, shield=True):
                await self._session.close()
                await self._on_close(self._id)


class WebSocketW3Guard(W3Guard):
    def __init__(
        self,
        id: int,
        w3: AsyncWeb3,
        on_idle: Callable[[int], Awaitable[None]],
        on_close: Callable[[int], Awaitable[None]],
        provider: WebsocketProviderV2,
    ):
        super().__init__(id, w3, on_idle, on_close)

        self._closed = False
        self._provider = provider

    async def close(self):
        if not self._closed:
            with move_on_after(5, shield=True):
                await self._provider.disconnect()
                await self._on_close(self._id)
                self._closed = True


class OtherW3Guard(W3Guard):
    def __init__(
        self,
        id: int,
        w3: AsyncWeb3,
        on_idle: Callable[[int], Awaitable[None]],
        on_close: Callable[[int], Awaitable[None]],
    ):
        super().__init__(id, w3, on_idle, on_close)

        self._closed = False

    async def close(self):
        if not self._closed:
            with move_on_after(5, shield=True):
                await self._on_close(self._id)
                self._closed = True


class W3Pool(object):
    def __init__(
        self,
        privkey: str,
        provider: Optional[AsyncBaseProvider] = None,
        provider_path: Optional[str] = None,
        pool_size: int = 1,
        timeout: int = 10,
    ) -> None:
        if privkey.startswith("0x"):
            privkey = privkey[2:]
        privkey_bytes = bytes.fromhex(privkey)
        self._privkey = keys.PrivateKey(privkey_bytes)
        self._pubkey: bytes = self._privkey.public_key.to_bytes()
        self._account: ChecksumAddress = self._privkey.public_key.to_checksum_address()

        self._pool_size = pool_size
        self._provider_path = provider_path
        self._timeout = timeout
        self._provider = None

        if provider is None:
            if provider_path is None:
                raise ValueError("provider and provider_path cannot be all None.")
            if provider_path.startswith("http"):
                self.provider_type = ProviderType.HTTP
            elif provider_path.startswith("ws"):
                self.provider_type = ProviderType.WS
            else:
                raise ValueError(f"unsupported provider {provider_path}")
        else:
            self.provider_type = ProviderType.Other
            self._provider = provider
            self._pool_size = 1
            if pool_size != 1:
                warnings.warn("Pool size can only be 1 when provider type is other")

        self._idle_pool = deque(maxlen=self._pool_size)

        self._condition = Condition()
        self._nonce_lock = Lock()

        self._next_id = 1
        self._guards: Dict[int, W3Guard] = {}

        self._closed = False

    async def on_guard_idle(self, id: int):
        async with self._condition:
            if id in self._guards:
                self._idle_pool.append(id)
                self._condition.notify(1)
                _logger.debug(f"w3 guard {id} is idle")

    async def on_guard_close(self, id: int):
        async with self._condition:
            if id in self._guards:
                self._guards.pop(id)
                if id in self._idle_pool:
                    self._idle_pool.remove(id)
                _logger.debug(f"w3 guard {id} is closed")

    @property
    def account(self) -> ChecksumAddress:
        return self._account

    @property
    def public_key(self) -> bytes:
        return self._pubkey

    async def _new_w3(self) -> W3Guard:
        if self.provider_type == ProviderType.HTTP:
            assert self._provider_path is not None
            provider = AsyncHTTPProvider(self._provider_path)
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            session = ClientSession(
                timeout=ClientTimeout(self._timeout),
                connector=TCPConnector(ssl=ssl_context),
                trust_env=True,
            )
            await provider.cache_async_session(session)
            w3 = AsyncWeb3(provider)
            guard = HTTPW3Guard(
                id=self._next_id,
                w3=w3,
                on_idle=self.on_guard_idle,
                on_close=self.on_guard_close,
                session=session,
            )
        elif self.provider_type == ProviderType.WS:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            provider = WebsocketProviderV2(
                self._provider_path,
                websocket_kwargs={
                    "open_timeout": self._timeout,
                    "close_timeout": self._timeout,
                    "ssl": ssl_context,
                },
            )
            w3 = AsyncWeb3.persistent_websocket(provider)
            await w3.provider.connect()
            guard = WebSocketW3Guard(
                id=self._next_id,
                w3=w3,
                on_idle=self.on_guard_idle,
                on_close=self.on_guard_close,
                provider=provider,
            )
        else:
            assert self._provider is not None
            w3 = AsyncWeb3(self._provider)
            guard = OtherW3Guard(
                id=self._next_id,
                w3=w3,
                on_idle=self.on_guard_idle,
                on_close=self.on_guard_close,
            )

        middleware = await async_construct_sign_and_send_raw_middleware(self._privkey)
        w3.middleware_onion.add(middleware)
        w3.eth.default_account = self._account

        self._next_id += 1

        return guard

    async def get(self) -> W3Guard:
        assert not self._closed, "w3 pool is closed"
        async with self._condition:
            if len(self._idle_pool) == 0 and len(self._guards) < self._pool_size:
                guard = await self._new_w3()
                self._guards[guard._id] = guard
                _logger.debug(f"new w3 guard {guard._id}")
                _logger.debug(f"w3 guard {guard._id} is in use")
                return guard
            while len(self._idle_pool) == 0 and (not self._closed):
                await self._condition.wait()

            if self._closed:
                raise ValueError("w3 pool is closed")

            guard_id = self._idle_pool.popleft()
            guard = self._guards[guard_id]
            _logger.debug(f"w3 guard {guard_id} is reused")
            return guard

    @asynccontextmanager
    async def with_nonce_lock(self):
        assert not self._closed, "w3 pool is closed"

        async with self._nonce_lock:
            yield

    async def close(self):
        if not self._closed:
            # not use `for guard in self._guards.values()`
            # because guard.close() will remove itself from the guards
            # and change directory size during iteration will raise a RuntimeError
            guards = list(self._guards.values())
            for guard in guards:
                await guard.close()

            async with self._condition:
                self._closed = True
                self._condition.notify_all()
            
            _logger.debug("w3 pool is closed")
