import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from crynux_server.models import TaskType

from .base import Base, BaseMixin


class DownloadModel(Base, BaseMixin):
    __tablename__ = "download_models"

    model_file_hash: Mapped[str] = mapped_column(
        sa.String(64), nullable=False, index=True
    )
    task_type: Mapped[TaskType] = mapped_column(
        sa.Enum(TaskType), nullable=False, index=False
    )
    source_type: Mapped[str] = mapped_column(sa.Text, nullable=False, index=False)
    repository: Mapped[str] = mapped_column(sa.Text, nullable=False, index=False)
    revision: Mapped[str] = mapped_column(sa.Text, nullable=False, index=False)
    format: Mapped[str] = mapped_column(sa.Text, nullable=False, index=False)
    format_kwargs: Mapped[str] = mapped_column(sa.Text, nullable=False, index=False)
