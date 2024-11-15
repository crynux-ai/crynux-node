from typing import get_args

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from crynux_server.models import TaskKind, TaskStatus, TaskType

from .base import Base, BaseMixin


class TaskState(Base, BaseMixin):
    __tablename__ = "task_states"

    task_id_commitment: Mapped[str] = mapped_column(
        sa.String(length=64), nullable=False, index=True
    )
    timeout: Mapped[int] = mapped_column(sa.Integer, nullable=False, index=False)
    status: Mapped[TaskStatus] = mapped_column(
        sa.Enum(TaskStatus), nullable=False, index=False
    )
    task_type: Mapped[TaskType] = mapped_column(
        sa.Enum(TaskType), nullable=False, index=False
    )
    files: Mapped[str] = mapped_column(sa.Text, nullable=False, index=False)
    score: Mapped[bytes] = mapped_column(
        sa.LargeBinary, nullable=False, index=False, default=b""
    )
    waiting_tx_hash: Mapped[bytes] = mapped_column(
        sa.BINARY, nullable=False, index=False, default=b""
    )
    waiting_tx_method: Mapped[str] = mapped_column(
        nullable=False, index=False, default=""
    )
    checkpoint: Mapped[str] = mapped_column(nullable=False, index=False, default="")


class TaskEvent(Base, BaseMixin):
    __tablename__ = "task_events"

    kind: Mapped[TaskKind] = mapped_column(
        sa.Enum(*get_args(TaskKind)),
        nullable=False,
    )

    event: Mapped[str] = mapped_column(sa.Text(), nullable=False)
