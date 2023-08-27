from enum import IntEnum


class NodeStatus(IntEnum):
    UNKNOWN = 0
    AVAILABLE = 1
    BUSY = 2
    PAUSED = 3
