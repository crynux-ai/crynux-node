from enum import IntEnum


class NodeStatus(IntEnum):
    QUIT = 0
    AVAILABLE = 1
    BUSY = 2
    PENDING_PAUSE = 3
    PENDING_QUIT = 4
    PAUSED = 5
