import logging
from contextlib import asynccontextmanager
from typing import Optional

from anyio import CancelScope, fail_after, get_cancelled_exc_class, sleep
from web3 import Web3

from crynux_server import models
from crynux_server.contracts import Contracts, TxOption, TxRevertedError

from .state_cache import ManagerStateCache

_logger = logging.getLogger(__name__)


class NodeStateManager(object):
    def __init__(
        self,
        state_cache: ManagerStateCache,
        contracts: Contracts,
    ):
        self.state_cache = state_cache
        self.contracts = contracts
        self._cancel_scope: Optional[CancelScope] = None

    async def _get_node_status(self):
        remote_status = await self.contracts.node_contract.get_node_status(
            self.contracts.account
        )
        local_status = models.convert_node_status(remote_status)
        return local_status

    async def _wait_for_running(self):
        local_status = await self._get_node_status()
        assert (
            local_status == models.NodeStatus.Running
        ), "Node status on chain is not running."
        await self.state_cache.set_node_state(local_status)
        await self.state_cache.set_tx_state(models.TxStatus.Success)

    async def _wait_for_stop(self):
        pending = True

        while True:
            local_status = await self._get_node_status()
            assert local_status in [
                models.NodeStatus.Stopped,
                models.NodeStatus.PendingStop,
            ], "Node status on chain is not stopped or pending."
            await self.state_cache.set_node_state(local_status)
            if pending:
                await self.state_cache.set_tx_state(models.TxStatus.Success)
                pending = False
            if local_status == models.NodeStatus.Stopped:
                break

    async def _wait_for_pause(self):
        pending = True

        while True:
            local_status = await self._get_node_status()
            assert local_status in [
                models.NodeStatus.Paused,
                models.NodeStatus.PendingPause,
            ], "Node status on chain is not paused or pending"
            await self.state_cache.set_node_state(local_status)
            if pending:
                await self.state_cache.set_tx_state(models.TxStatus.Success)
                pending = False
            if local_status == models.NodeStatus.Paused:
                break

    async def start_sync(self, interval: float = 5):
        assert self._cancel_scope is None, "NodeStateManager has started synchronizing."

        try:
            with CancelScope() as scope:
                self._cancel_scope = scope

                while True:
                    local_status = await self._get_node_status()
                    await self.state_cache.set_node_state(local_status)
                    await sleep(interval)
        finally:
            self._cancel_scope = None

    def stop_sync(self):
        if self._cancel_scope is not None and not self._cancel_scope.cancel_called:
            self._cancel_scope.cancel()

    @asynccontextmanager
    async def _wrap_tx_error(self):
        try:
            yield
        except KeyboardInterrupt:
            raise
        except get_cancelled_exc_class():
            raise
        except (TxRevertedError, AssertionError, ValueError) as e:
            _logger.error(f"tx error {str(e)}")
            with fail_after(5, shield=True):
                await self.state_cache.set_tx_state(models.TxStatus.Error, str(e))
            raise
        except Exception as e:
            _logger.exception(e)
            _logger.error("unknown tx error")
            raise

    async def try_start(
        self, gpu_name: str, gpu_vram: int, interval: float = 5, *, option: "Optional[TxOption]" = None
    ):
        while True:
            status = await self.contracts.node_contract.get_node_status(
                self.contracts.account
            )
            if status in [
                models.ChainNodeStatus.AVAILABLE,
                models.ChainNodeStatus.BUSY,
            ]:
                _logger.info("Node has joined in the network.")
                break
            elif status in [
                models.ChainNodeStatus.PENDING_PAUSE,
                models.ChainNodeStatus.PENDING_QUIT,
            ]:
                await sleep(interval)
                continue

            elif status == models.ChainNodeStatus.QUIT:
                node_amount = Web3.to_wei(400, "ether")
                balance = await self.contracts.token_contract.balance_of(
                    self.contracts.account
                )
                if balance < node_amount:
                    raise ValueError("Node token balance is not enough to join.")
                allowance = await self.contracts.token_contract.allowance(
                    self.contracts.node_contract.address
                )
                if allowance < node_amount:
                    waiter = await self.contracts.token_contract.approve(
                        self.contracts.node_contract.address,
                        node_amount,
                        option=option,
                    )
                    await waiter.wait()
                waiter = await self.contracts.node_contract.join(
                    gpu_name=gpu_name,
                    gpu_vram=gpu_vram,
                    option=option,
                )
                # update tx state to avoid the web user controlling node status by api
                # it's the same in try_stop method
                await self.state_cache.set_tx_state(models.TxStatus.Pending)
                await waiter.wait()
                await self._wait_for_running()
            elif status == models.ChainNodeStatus.PAUSED:
                waiter = await self.contracts.node_contract.resume(option=option)
                await self.state_cache.set_tx_state(models.TxStatus.Pending)
                await waiter.wait()
                await self._wait_for_running()

            _logger.info("Node joins in the network successfully.")
            break

    async def try_stop(self, *, option: "Optional[TxOption]" = None):
        status = await self.contracts.node_contract.get_node_status(
            self.contracts.account
        )
        if status == models.ChainNodeStatus.AVAILABLE:
            waiter = await self.contracts.node_contract.quit(option=option)
            await self.state_cache.set_tx_state(models.TxStatus.Pending)
            await waiter.wait()
            # dont need to update node status because in non-headless mode the sync-state method will update it,
            # and in headless mode the node status is useless
            await self.state_cache.set_tx_state(models.TxStatus.Success)
            _logger.info("Node leaves the network successfully.")
        else:
            _logger.info(
                f"Node status is {models.convert_node_status(status)}, cannot leave the network automatically"
            )

    async def start(
        self,
        gpu_name: str,
        gpu_vram: int,
        *,
        option: "Optional[TxOption]" = None,
    ):
        async with self._wrap_tx_error():
            node_status = (await self.state_cache.get_node_state()).status
            tx_status = (await self.state_cache.get_tx_state()).status
            assert (
                node_status == models.NodeStatus.Stopped
            ), "Cannot start node. Node is not stopped."
            assert (
                tx_status != models.TxStatus.Pending
            ), "Cannot start node. Last transaction is in pending."

            node_amount = Web3.to_wei(400, "ether")
            balance = await self.contracts.token_contract.balance_of(
                self.contracts.account
            )
            if balance < node_amount:
                raise ValueError("Node token balance is not enough to join.")
            allowance = await self.contracts.token_contract.allowance(
                self.contracts.node_contract.address
            )
            if allowance < node_amount:
                waiter = await self.contracts.token_contract.approve(
                    self.contracts.node_contract.address, node_amount, option=option
                )
                await waiter.wait()

            waiter = await self.contracts.node_contract.join(
                gpu_name=gpu_name,
                gpu_vram=gpu_vram,
                option=option,
            )
            await self.state_cache.set_tx_state(models.TxStatus.Pending)

        async def wait():
            async with self._wrap_tx_error():
                await waiter.wait()

                await self._wait_for_running()

        return wait

    async def stop(
        self,
        *,
        option: "Optional[TxOption]" = None,
    ):
        async with self._wrap_tx_error():
            node_status = (await self.state_cache.get_node_state()).status
            tx_status = (await self.state_cache.get_tx_state()).status
            assert (
                node_status == models.NodeStatus.Running
            ), "Cannot stop node. Node is not running."
            assert (
                tx_status != models.TxStatus.Pending
            ), "Cannot start node. Last transaction is in pending."

            waiter = await self.contracts.node_contract.quit(option=option)
            await self.state_cache.set_tx_state(models.TxStatus.Pending)

        async def wait():
            async with self._wrap_tx_error():
                await waiter.wait()

                await self._wait_for_stop()

        return wait

    async def pause(
        self,
        *,
        option: "Optional[TxOption]" = None,
    ):
        async with self._wrap_tx_error():
            node_status = (await self.state_cache.get_node_state()).status
            tx_status = (await self.state_cache.get_tx_state()).status
            assert (
                node_status == models.NodeStatus.Running
            ), "Cannot stop node. Node is not running."
            assert (
                tx_status != models.TxStatus.Pending
            ), "Cannot start node. Last transaction is in pending."

            waiter = await self.contracts.node_contract.pause(option=option)
            await self.state_cache.set_tx_state(models.TxStatus.Pending)

        async def wait():
            async with self._wrap_tx_error():
                await waiter.wait()

                await self._wait_for_pause()

        return wait

    async def resume(
        self,
        *,
        option: "Optional[TxOption]" = None,
    ):
        async with self._wrap_tx_error():
            node_status = (await self.state_cache.get_node_state()).status
            tx_status = (await self.state_cache.get_tx_state()).status
            assert (
                node_status == models.NodeStatus.Paused
            ), "Cannot stop node. Node is not running."
            assert (
                tx_status != models.TxStatus.Pending
            ), "Cannot start node. Last transaction is in pending."

            waiter = await self.contracts.node_contract.resume(option=option)
            await self.state_cache.set_tx_state(models.TxStatus.Pending)

        async def wait():
            async with self._wrap_tx_error():
                await waiter.wait()

                await self._wait_for_running()

        return wait


_default_state_manager: Optional[NodeStateManager] = None


def get_node_state_manager() -> NodeStateManager:
    assert _default_state_manager is not None, "NodeStateManager has not been set."

    return _default_state_manager


def set_node_state_manager(manager: NodeStateManager):
    global _default_state_manager

    _default_state_manager = manager
