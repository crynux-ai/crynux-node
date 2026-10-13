from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from crynux_server import models
from crynux_server.node_manager import state_manager as state_manager_module
from crynux_server.node_manager.state_manager import NodeStateManager

MODEL_FILE_A = models.ModelFileEntry(
    repository="org/model-a", revision="rev-a", format="diffusers"
)
MODEL_FILE_B = models.ModelFileEntry(repository="org/model-b", revision="rev-b")


def make_state_manager():
    config = MagicMock()
    config.ethereum.network = "dymension"
    state_cache = MagicMock()
    state_cache.set_node_state = AsyncMock()
    state_cache.set_tx_state = AsyncMock()
    state_cache.get_tx_state = AsyncMock(
        return_value=SimpleNamespace(status=models.TxStatus.Success)
    )
    download_model_cache = MagicMock()
    download_model_cache.load_all = AsyncMock(
        return_value=[
            models.DownloadedModel(task_type=models.TaskType.SD, model_file=MODEL_FILE_A),
            models.DownloadedModel(task_type=models.TaskType.LLM, model_file=MODEL_FILE_B),
        ]
    )
    contracts = MagicMock()
    relay = MagicMock()
    relay.node_resume = AsyncMock()
    relay.node_sync_capabilities = AsyncMock()
    relay.node_join = AsyncMock()
    manager = NodeStateManager(
        config=config,
        state_cache=state_cache,
        download_model_cache=download_model_cache,
        contracts=contracts,
        relay=relay,
    )
    return manager, relay


async def test_try_start_syncs_capabilities_when_already_joined():
    manager, relay = make_state_manager()
    manager._get_node_status = AsyncMock(return_value=models.NodeStatus.Running)

    await manager.try_start(
        gpu_name="RTX 4090+docker",
        gpu_vram=24,
        version=[3, 2, 0],
    )

    relay.node_sync_capabilities.assert_awaited_once_with(
        gpu_name="RTX 4090+docker",
        gpu_vram=24,
        model_files=[MODEL_FILE_A, MODEL_FILE_B],
        version="3.2.0",
    )
    relay.node_resume.assert_not_awaited()


async def test_try_start_syncs_capabilities_after_resume():
    manager, relay = make_state_manager()
    manager._get_node_status = AsyncMock(
        side_effect=[
            models.NodeStatus.Paused,
            models.NodeStatus.Paused,
            models.NodeStatus.Paused,
            models.NodeStatus.Running,
        ]
    )

    await manager.try_start(
        gpu_name="RTX 4090+docker",
        gpu_vram=24,
        version=[3, 2, 0],
    )

    relay.node_resume.assert_awaited_once()
    relay.node_sync_capabilities.assert_awaited_once_with(
        gpu_name="RTX 4090+docker",
        gpu_vram=24,
        model_files=[MODEL_FILE_A, MODEL_FILE_B],
        version="3.2.0",
    )


async def test_join_and_capability_sync_report_identical_model_files(monkeypatch):
    manager, relay = make_state_manager()
    monkeypatch.setattr(state_manager_module, "get_staking_amount", lambda: 400)
    manager._get_node_status = AsyncMock(
        side_effect=[
            models.NodeStatus.Stopped,
            models.NodeStatus.Stopped,
            models.NodeStatus.Stopped,
            models.NodeStatus.Running,
        ]
    )
    manager._ensure_start_balance = AsyncMock()
    manager._send_stake_tx = AsyncMock(return_value=None)

    await manager.try_start(
        gpu_name="RTX 4090+docker",
        gpu_vram=24,
        version=[3, 2, 0],
    )
    await manager._sync_capabilities("RTX 4090+docker", 24, [3, 2, 0])

    join_files = relay.node_join.await_args.kwargs["model_files"]
    sync_files = relay.node_sync_capabilities.await_args.kwargs["model_files"]
    assert join_files == [MODEL_FILE_A, MODEL_FILE_B]
    assert join_files == sync_files
    assert all(entry.revision != "" for entry in join_files)
