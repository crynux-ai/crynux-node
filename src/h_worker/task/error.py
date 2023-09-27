class TaskError(Exception):
    def __init__(self, field: str, msg: str) -> None:
        self.field = field
        self.msg = msg
        error_msg = f"Task config field '{field}' error for {msg}"
        super().__init__(error_msg)
