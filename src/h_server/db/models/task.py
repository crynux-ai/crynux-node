from typing import get_args, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime


from h_server.models import TaskKind, TaskStatus

from .base import Base, BaseMixin


class TaskState(Base, BaseMixin):
    __tablename__ = "task_states"

    task_id: Mapped[int] = mapped_column(sa.Integer, nullable=False, index=True)
    round: Mapped[int] = mapped_column(sa.Integer, nullable=False, index=False)
    status: Mapped[TaskStatus] = mapped_column(
        sa.Enum(TaskStatus), nullable=False, index=False
    )
    files: Mapped[str] = mapped_column(sa.Text, nullable=False, index=False)
    result: Mapped[bytes] = mapped_column(
        sa.LargeBinary, nullable=False, index=False, default=b""
    )


class TaskEvent(Base, BaseMixin):
    __tablename__ = "task_events"

    kind: Mapped[TaskKind] = mapped_column(
        sa.Enum(*get_args(TaskKind)),
        nullable=False,
    )

    event: Mapped[str] = mapped_column(sa.Text(), nullable=False)
