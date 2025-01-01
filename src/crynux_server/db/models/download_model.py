from typing import Literal, Optional, get_args

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from crynux_server.models import TaskType

from .base import Base, BaseMixin


ModelType = Literal["base", "lora", "controlnet"]


class DownloadModel(Base, BaseMixin):
    __tablename__ = "download_models"

    model_id_hash: Mapped[str] = mapped_column(
        sa.String(64), nullable=False, index=True
    )
    task_type: Mapped[TaskType] = mapped_column(
        sa.Enum(TaskType), nullable=False, index=False
    )
    model_name: Mapped[str] = mapped_column(sa.Text, nullable=False, index=False)
    model_type: Mapped[ModelType] = mapped_column(
        sa.Enum(*get_args(ModelType), ), nullable=False, index=False
    )
    variant: Mapped[Optional[str]] = mapped_column(
        sa.String(10), nullable=True, index=False, default=None
    )
