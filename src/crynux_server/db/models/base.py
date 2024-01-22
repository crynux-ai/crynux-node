from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import (DeclarativeBase, Mapped, MappedAsDataclass,
                            mapped_column)

__all__ = ["BaseMixin"]


class Base(DeclarativeBase, MappedAsDataclass):
    pass


class BaseMixin(MappedAsDataclass):
    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        init=False,
        default_factory=datetime.now,
        insert_default=datetime.now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        init=False,
        default_factory=datetime.now,
        onupdate=datetime.now,
        insert_default=datetime.now,
    )
