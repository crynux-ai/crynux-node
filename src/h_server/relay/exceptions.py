class RelayError(Exception):
    def __init__(self, status_code: int, method: str, message: str) -> None:
        self.status_code = status_code
        self.method = method
        self.message = message

    def __str__(self) -> str:
        return f"Relay {self.method} failed: {self.status_code} {self.message}"
