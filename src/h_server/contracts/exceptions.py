class TxRevertedError(Exception):
    def __init__(self, method: str, reason: str) -> None:
        self.method = method
        self.reason = reason

    def __str__(self) -> str:
        return f"{self.method} is reverted, reason {self.reason}"

    def __repr__(self) -> str:
        return f"TxReverted(method={self.method}, reason={self.reason})"
