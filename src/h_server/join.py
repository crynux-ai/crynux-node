import logging
from contextlib import asynccontextmanager

from anyio import move_on_after

from web3 import Web3
from h_server.contracts import Contracts, TxRevertedError
from h_server.models import NodeStatus

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def node_join(contracts: Contracts):
    try:
        status = await contracts.node_contract.get_node_status(contracts.account)
        if status == NodeStatus.UNKNOWN:
            node_amount = Web3.to_wei(400, "ether")
            balance = await contracts.token_contract.balance_of(contracts.account)
            if balance < node_amount:
                raise ValueError("Node token balance is not enough to join.")
            allowance = await contracts.token_contract.allowance(
                contracts.node_contract.address
            )
            if allowance < node_amount:
                await contracts.token_contract.approve(
                    contracts.node_contract.address, node_amount
                )

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
