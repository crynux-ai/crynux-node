import re


class TaskCancelled(Exception):
    pass


class TaskError(Exception):
    error_type = "TaskError"

    def __init__(self, msg: str):
        self.msg = msg

    def __str__(self) -> str:
        return f"{self.error_type}, error msg:\n{self.msg}\n"


class TaskInvalid(TaskError):
    error_type = "TaskInvalid"


class TaskExecutionError(TaskError):
    error_type = "TaskExecutionError"


class PrefetchError(TaskError):
    error_type = "PrefetchError"


def is_task_invalid(stdout: str) -> bool:
    pattern = re.compile(r"Task args invalid|Task model invalid")
    return pattern.search(stdout) is not None
