import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from h_server.models import NodeStatus

from .base import Base, BaseMixin


class NodeState(Base, BaseMixin):
    __tablename__ = "node_state"

    status: Mapped[NodeStatus] = mapped_column(
        sa.Enum(NodeStatus), index=True, nullable=False
    )
    message: Mapped[str] = mapped_column(default="", index=False, nullable=False)
