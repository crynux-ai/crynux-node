from enum import Enum

from pydantic import BaseModel


class TxStatus(Enum):
    Success = ""
    Pending = "pending"
    Error = "error"


class TxState(BaseModel):
    status: TxStatus
    error: str = ""
