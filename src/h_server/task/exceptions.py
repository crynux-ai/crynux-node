from enum import Enum


class TaskErrorSource(str, Enum):
    Relay = "relay"
    Contracts = "contracts"
    Celery = "celery"
    Unknown = "unknown"


class TaskError(Exception):
    def __init__(self, message: str, source: TaskErrorSource, retry: bool) -> None:
        super().__init__(message)

        self.message = message
        self.source = source
        self.retry = retry


class TaskFailure(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
