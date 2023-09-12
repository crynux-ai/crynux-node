from datetime import datetime
from typing import Optional

import sqlalchemy as sa

from h_server import db
from h_server.db import models as db_models
from h_server.models import TaskState, TaskStatus

from .abc import TaskStateCache


class DbTaskStateCache(TaskStateCache):
    async def load(self, task_id: int) -> TaskState:
        async with db.session_scope() as sess:
            q = (
                sa.select(db_models.TaskState)
                .where(db_models.TaskState.task_id == task_id)
                .where(db_models.TaskState.deleted_at.is_(None))
            )
            state = (await sess.scalars(q)).one_or_none()
            if state is not None:
                files = state.files.split(",")
                return TaskState(
                    task_id=task_id,
                    round=state.round,
                    status=state.status,
                    files=files,
                    result=state.result,
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
                    status=task_state.status,
                    files=",".join(task_state.files),
                    result=task_state.result,
                )
                sess.add(state)
            elif state.deleted_at is None:
                state.round = task_state.round
                state.status = task_state.status
                state.result = task_state.result
            else:
                raise KeyError(f"Task state of {task_id} has been deleted.")
            await sess.commit()

    async def has(self, task_id: int) -> bool:
        async with db.session_scope() as sess:
            q = sa.select(db_models.TaskState).where(
                db_models.TaskState.task_id == task_id
            )
            state = (await sess.scalars(q)).one_or_none()
            return state is not None and state.deleted_at is None

    async def delete(self, task_id: int):
        async with db.session_scope() as sess:
            q = sa.select(db_models.TaskState).where(
                db_models.TaskState.task_id == task_id
            )
            state = (await sess.scalars(q)).one_or_none()
            if state is not None and state.deleted_at is None:
                state.deleted_at = datetime.now()
            await sess.commit()

    async def count(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        deleted: Optional[bool] = None,
        status: Optional[TaskStatus] = None
    ):
        async with db.session_scope() as sess:
            q = sa.select(sa.func.count(db_models.TaskState.id))
            if start is not None:
                q = q.where(db_models.TaskState.updated_at >= start)
            if end is not None:
                q = q.where(db_models.TaskState.updated_at < end)
            if deleted is not None:
                if deleted:
                    q = q.where(db_models.TaskState.deleted_at.is_not(None))
                else:
                    q = q.where(db_models.TaskState.deleted_at.is_(None))
            if status is not None:
                q = q.where(db_models.TaskState.status == status)

            n = (await sess.execute(q)).scalar_one()
            return n
