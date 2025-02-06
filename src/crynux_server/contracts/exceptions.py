class TxRevertedError(Exception):
    def __init__(self, method: str, tx_hash: str, reason: str) -> None:
        self.method = method
        self.tx_hash = tx_hash
        self.reason = reason

    def __str__(self) -> str:
        return f"{self.method} is reverted, tx hash: {self.tx_hash}, reason {self.reason}"

    def __repr__(self) -> str:
        return f"TxReverted(method={self.method}, tx_hash={self.tx_hash}, reason={self.reason})"
