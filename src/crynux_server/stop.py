import logging
from typing import Type, Optional

import anyio

from crynux_server import db, log, models
from crynux_server.config import get_config, TxOption
from crynux_server.contracts import Contracts
from crynux_server.node_manager import ManagerStateCache, NodeStateManager
from crynux_server.node_manager.state_cache import (
    DbNodeStateCache,
    DbTxStateCache,
    StateCache,
)

_logger = logging.getLogger(__name__)


async def _stop(
    state_manager: Optional[NodeStateManager] = None,
    contracts: Optional[Contracts] = None,
    state_cache: Optional[ManagerStateCache] = None,
    node_state_cache_cls: Type[StateCache[models.NodeState]] = DbNodeStateCache,
    tx_state_cache_cls: Type[StateCache[models.TxState]] = DbTxStateCache,
    option: Optional[TxOption] = None,
):
    config = get_config()

    log.init(config)

    if len(config.db) > 0:
        await db.init(config.db)

    if state_manager is None:
        if contracts is None:
            assert (
                len(config.ethereum.privkey) > 0
            ), "You must provide private key in config file before stoping node."
            contracts = Contracts(
                provider_path=config.ethereum.provider,
                privkey=config.ethereum.privkey,
            )
            await contracts.init(
                token_contract_address=config.ethereum.contract.token,
                node_contract_address=config.ethereum.contract.node,
                task_contract_address=config.ethereum.contract.task,
                qos_contract_address=config.ethereum.contract.qos,
                task_queue_contract_address=config.ethereum.contract.task_queue,
                netstats_contract_address=config.ethereum.contract.netstats,
            )
        if state_cache is None:
            state_cache = ManagerStateCache(
                node_state_cache_cls=node_state_cache_cls,
                tx_state_cache_cls=tx_state_cache_cls,
            )
        state_manager = NodeStateManager(state_cache=state_cache, contracts=contracts)

    try:
        waiter = await state_manager.stop(option=option)
        await waiter()
        _logger.info("Stop the node successfully")
    except Exception:
        _logger.error("Cannot stop the node")
        raise


def stop(
    state_manager: Optional[NodeStateManager] = None,
    contracts: Optional[Contracts] = None,
    state_cache: Optional[ManagerStateCache] = None,
    node_state_cache_cls: Type[StateCache[models.NodeState]] = DbNodeStateCache,
    tx_state_cache_cls: Type[StateCache[models.TxState]] = DbTxStateCache,
    option: Optional[TxOption] = None,
):
    try:
        anyio.run(
            _stop,
            state_manager,
            contracts,
            state_cache,
            node_state_cache_cls,
            tx_state_cache_cls,
            option
        )
    except KeyboardInterrupt:
        pass
