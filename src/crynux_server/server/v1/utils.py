from typing import Optional

from pydantic import BaseModel


class CommonResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None
