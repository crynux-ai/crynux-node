import logging
from contextlib import asynccontextmanager

from anyio import move_on_after

from h_server.contracts import Contracts, TxRevertedError
from h_server.models import NodeStatus

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def node_join(contracts: Contracts):
    try:
        status = await contracts.node_contract.get_node_status(contracts.account)
        if status == NodeStatus.UNKNOWN:
            await contracts.node_contract.join()
        elif status == NodeStatus.PAUSED:
            await contracts.node_contract.resume()
        yield
    finally:
        with move_on_after(delay=5, shield=True):
            try:
                await contracts.node_contract.pause()
            except TxRevertedError as e:
                _logger.error("Node cannot pause during termination")
                _logger.error(str(e))
