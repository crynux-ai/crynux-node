from datetime import datetime
from typing import Optional, List

import sqlalchemy as sa

from crynux_server import db
from crynux_server.db import models as db_models
from crynux_server.models import TaskState, TaskStatus

from .abc import TaskStateCache


class DbTaskStateCache(TaskStateCache):
    async def load(self, task_id: int) -> TaskState:
        async with db.session_scope() as sess:
            q = sa.select(db_models.TaskState).where(
                db_models.TaskState.task_id == task_id
            )
            state = (await sess.scalars(q)).one_or_none()
            if state is not None:
                files = state.files.split(",")
                return TaskState(
                    task_id=task_id,
                    round=state.round,
                    timeout=state.timeout,
                    status=state.status,
                    files=files,
                    result=state.result,
                    disclosed=state.disclosed,
                    waiting_tx_hash=state.waiting_tx_hash,
                    waiting_tx_method=state.waiting_tx_method,
                )
            else:
                raise KeyError(f"Task state of {task_id} not found.")

    async def dump(self, task_state: TaskState):
        async with db.session_scope() as sess:
            task_id = task_state.task_id

            q = sa.select(db_models.TaskState).where(
                db_models.TaskState.task_id == task_id
            )
            state = (await sess.scalars(q)).one_or_none()
            if state is None:
                state = db_models.TaskState(
                    task_id=task_id,
                    round=task_state.round,
                    timeout=task_state.timeout,
                    status=task_state.status,
                    files=",".join(task_state.files),
                    result=task_state.result,
                    disclosed=task_state.disclosed,
                    waiting_tx_hash=task_state.waiting_tx_hash,
                    waiting_tx_method=task_state.waiting_tx_method,
                )
                sess.add(state)
            else:
                state.round = task_state.round
                state.timeout = task_state.timeout
                state.status = task_state.status
                state.files = ",".join(task_state.files)
                state.result = task_state.result
                state.disclosed = task_state.disclosed
                state.waiting_tx_hash = task_state.waiting_tx_hash
                state.waiting_tx_method = task_state.waiting_tx_method
            await sess.commit()

    async def has(self, task_id: int) -> bool:
        async with db.session_scope() as sess:
            q = sa.select(db_models.TaskState).where(
                db_models.TaskState.task_id == task_id
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
                    task_id=state.task_id,
                    round=state.round,
                    timeout=state.timeout,
                    status=state.status,
                    files=state.files.split(","),
                    result=state.result,
                    disclosed=state.disclosed,
                    waiting_tx_hash=state.waiting_tx_hash,
                    waiting_tx_method=state.waiting_tx_method,
                )
                for state in states
            ]
