from datetime import datetime
from typing import Optional, List

import sqlalchemy as sa

from crynux_server import db
from crynux_server.db import models as db_models
from crynux_server.models import TaskState, TaskStatus

from .abc import TaskStateCache


class DbTaskStateCache(TaskStateCache):
    async def load(self, task_id_commitment: bytes) -> TaskState:
        async with db.session_scope() as sess:
            q = sa.select(db_models.TaskState).where(
                db_models.TaskState.task_id_commitment == task_id_commitment.hex()
            )
            state = (await sess.scalars(q)).one_or_none()
            if state is not None:
                files = state.files.split(",")
                return TaskState(
                    task_id_commitment=bytes.fromhex(state.task_id_commitment),
                    timeout=state.timeout,
                    status=state.status,
                    task_type=state.task_type,
                    files=files,
                    score=state.score,
                    waiting_tx_hash=state.waiting_tx_hash,
                    waiting_tx_method=state.waiting_tx_method,
                    checkpoint=state.checkpoint,
                )
            else:
                raise KeyError(f"Task state of {task_id_commitment.hex()} not found.")

    async def dump(self, task_state: TaskState):
        async with db.session_scope() as sess:
            task_id_commitment = task_state.task_id_commitment

            q = sa.select(db_models.TaskState).where(
                db_models.TaskState.task_id_commitment == task_id_commitment.hex()
            )
            state = (await sess.scalars(q)).one_or_none()
            if state is None:
                state = db_models.TaskState(
                    task_id_commitment=task_id_commitment.hex(),
                    timeout=task_state.timeout,
                    status=task_state.status,
                    task_type=task_state.task_type,
                    files=",".join(task_state.files),
                    score=task_state.score,
                    waiting_tx_hash=task_state.waiting_tx_hash,
                    waiting_tx_method=task_state.waiting_tx_method,
                    checkpoint=task_state.checkpoint,
                )
                sess.add(state)
            else:
                state.timeout = task_state.timeout
                state.status = task_state.status
                state.task_type = task_state.task_type
                state.files = ",".join(task_state.files)
                state.score = task_state.score
                state.waiting_tx_hash = task_state.waiting_tx_hash
                state.waiting_tx_method = task_state.waiting_tx_method
                state.checkpoint = task_state.checkpoint
            await sess.commit()

    async def has(self, task_id_commitment: bytes) -> bool:
        async with db.session_scope() as sess:
            q = sa.select(db_models.TaskState).where(
                db_models.TaskState.task_id_commitment == task_id_commitment.hex()
            )
            state = (await sess.scalars(q)).one_or_none()
            return state is not None

    async def find(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        status: Optional[List[TaskStatus]] = None,
    ) -> List[TaskState]:
        async with db.session_scope() as sess:
            q = sa.select(db_models.TaskState)
            if start is not None:
                q = q.where(db_models.TaskState.updated_at >= start)
            if end is not None:
                q = q.where(db_models.TaskState.updated_at < end)
            if status is not None:
                q = q.where(db_models.TaskState.status.in_(status))

            states = (await sess.execute(q)).scalars().all()
            return [
                TaskState(
                    task_id_commitment=bytes.fromhex(state.task_id_commitment[2:]),
                    timeout=state.timeout,
                    status=state.status,
                    task_type=state.task_type,
                    files=state.files.split(","),
                    score=state.score,
                    waiting_tx_hash=state.waiting_tx_hash,
                    waiting_tx_method=state.waiting_tx_method,
                    checkpoint=state.checkpoint,
                )
                for state in states
            ]
