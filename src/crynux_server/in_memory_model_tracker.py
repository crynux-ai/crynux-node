import logging
from typing import TYPE_CHECKING, Optional

from anyio import Lock

from crynux_server.models import InMemoryModel, RelayTask

if TYPE_CHECKING:
    from crynux_server.relay.abc import Relay

_logger = logging.getLogger(__name__)

_UNREPORTED = object()


def build_in_memory_model(
    task: RelayTask,
    execution_dtype: Optional[str],
    model_cache_hash: Optional[str],
) -> Optional[InMemoryModel]:
    """Describe the model held in memory after a successful execution.

    The Relay-assigned requested hash, the frozen exact files, and the
    Relay-provided canonical config are reported unchanged. The model is
    described only when the Runner returned the requested hash as the identity
    of the model now in memory."""
    requested = task.requested_model_cache_hash
    if requested is None or model_cache_hash != requested:
        return None
    if (
        task.requested_model_cache_config is None
        or len(task.execution_model_files) == 0
        or execution_dtype is None
    ):
        return None
    return InMemoryModel(
        model_cache_hash=requested,
        model_cache_config=task.requested_model_cache_config,
        model_files=task.execution_model_files,
        execution_dtype=execution_dtype,
    )


class InMemoryModelTracker(object):
    """The single nullable in-memory model state of the inference worker.

    Local updates are applied immediately. `sync` reports the latest local
    state to the Relay, one report at a time. Every worker connection reset
    advances the epoch, so a result produced by a previous worker lifetime
    cannot overwrite the empty state of the current one."""

    def __init__(self) -> None:
        self._current: Optional[InMemoryModel] = None
        self._reported = _UNREPORTED
        self._epoch = 0
        self._lock = Lock()

    @property
    def epoch(self) -> int:
        return self._epoch

    @property
    def current(self) -> Optional[InMemoryModel]:
        return self._current

    def reset(self):
        """The worker holds no model: its process restarted or disconnected."""
        self._epoch += 1
        self._current = None

    def set(self, model: Optional[InMemoryModel], epoch: int):
        """Replace the state with the outcome of an execution that started in `epoch`."""
        if epoch != self._epoch:
            return
        self._current = model

    def invalidate(self):
        """Forget the reported state so the next sync reports it again."""
        self._reported = _UNREPORTED

    async def sync(self, relay: "Relay"):
        async with self._lock:
            target = self._current
            if self._reported is not _UNREPORTED and target == self._reported:
                return
            await relay.node_report_in_memory_model(target)
            self._reported = target
            _logger.info(
                "Reported in-memory model: %s",
                "empty" if target is None else target.model_cache_hash,
            )


_default_tracker: Optional[InMemoryModelTracker] = None


def get_in_memory_model_tracker() -> InMemoryModelTracker:
    global _default_tracker
    if _default_tracker is None:
        _default_tracker = InMemoryModelTracker()
    return _default_tracker
