import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, BaseMixin


class BlockNumber(Base, BaseMixin):
    __tablename__ = "block_number"

    number: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, index=False, default=0
    )
