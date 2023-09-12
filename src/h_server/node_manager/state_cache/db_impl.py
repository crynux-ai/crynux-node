import sqlalchemy as sa

from h_server import db
from h_server.models import NodeState, NodeStatus

from .abc import NodeStateCache


class DbNodeStateCache(NodeStateCache):
    async def get(self) -> NodeState:
        async with db.session_scope() as sess:
            q = sa.select(db.models.NodeState).where(db.models.NodeState.id == 1)
            state = (await sess.execute(q)).scalar_one_or_none()
            if state is None:
                return NodeState(status=NodeStatus.Init)
            else:
                return NodeState(status=state.status, message=state.message)

    async def set(self, state: NodeState):
        async with db.session_scope() as sess:
            q = sa.select(db.models.NodeState).where(db.models.NodeState.id == 1)
            db_state = (await sess.execute(q)).scalar_one_or_none()
            if db_state is None:
                db_state = db.models.NodeState(
                    status=state.status, message=state.message
                )
                sess.add(db_state)
            else:
                db_state.status = state.status
                db_state.message = state.message
            await sess.commit()
