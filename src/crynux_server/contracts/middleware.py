from typing import Any, Callable

from limiter import get_limiter, limit
from web3 import AsyncWeb3
from web3.types import RPCEndpoint, RPCResponse


async def async_construct_rate_limit_middleware(rps: int):
    limiter = get_limiter(rate=rps, capacity=rps // 2)
    limit_eth_call = limit(limiter=limiter)

    async def async_rate_limit_middleware(
        make_request: Callable[[RPCEndpoint, Any], Any], async_w3: AsyncWeb3
    ):
        async def middleware(method: RPCEndpoint, params: Any) -> RPCResponse:
            async with limit_eth_call:
                return await make_request(method, params)

        return middleware

    return async_rate_limit_middleware
