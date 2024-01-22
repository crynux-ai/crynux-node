import sqlalchemy as sa

from crynux_server import db
from crynux_server.models import NodeState, NodeStatus, TxState, TxStatus
from crynux_server.models.tx import TxState

from .abc import StateCache


class DbNodeStateCache(StateCache[NodeState]):
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


class DbTxStateCache(StateCache[TxState]):
    async def get(self) -> TxState:
        async with db.session_scope() as sess:
            q = sa.select(db.models.TxState).where(db.models.TxState.id == 1)
            state = (await sess.execute(q)).scalar_one_or_none()
            if state is None:
                return TxState(status=TxStatus.Success)
            else:
                return TxState(status=state.status, error=state.error)

    async def set(self, state: TxState):
        async with db.session_scope() as sess:
            q = sa.select(db.models.TxState).where(db.models.TxState.id == 1)
            db_state = (await sess.execute(q)).scalar_one_or_none()
            if db_state is None:
                db_state = db.models.TxState(status=state.status, error=state.error)
                sess.add(db_state)
            else:
                db_state.status = state.status
                db_state.error = state.error
            await sess.commit()
