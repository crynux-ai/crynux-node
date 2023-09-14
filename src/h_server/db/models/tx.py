import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from h_server.models import TxStatus

from .base import Base, BaseMixin


class TxState(Base, BaseMixin):
    __tablename__ = "tx_state"

    status: Mapped[TxStatus] = mapped_column(
        sa.Enum(TxStatus), index=True, nullable=False
    )
    error: Mapped[str] = mapped_column(default="", index=False, nullable=False)
