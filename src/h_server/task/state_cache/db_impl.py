from .abc import TaskStateCache
from datetime import datetime

import sqlalchemy as sa
from h_server import db
from h_server.db import models as db_models
from h_server.models import TaskState


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
