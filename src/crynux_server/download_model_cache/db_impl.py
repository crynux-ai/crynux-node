import json
from typing import List

import sqlalchemy as sa

import crynux_server.db.models as db_models
from crynux_server import db
from crynux_server.models import DownloadedModel, ModelFileEntry

from .abc import DownloadModelCache


class DbDownloadModelCache(DownloadModelCache):
    async def save(self, model: DownloadedModel):
        async with db.session_scope() as sess:
            model_file_hash = model.model_file.digest()

            q = sa.select(db_models.DownloadModel).where(
                db_models.DownloadModel.model_file_hash == model_file_hash
            )
            m = (await sess.scalars(q)).one_or_none()
            if m is None:
                entry = model.model_file
                m = db_models.DownloadModel(
                    model_file_hash=model_file_hash,
                    task_type=model.task_type,
                    source_type=entry.source_type,
                    repository=entry.repository,
                    revision=entry.revision,
                    format=entry.format,
                    format_kwargs=json.dumps(entry.format_kwargs, sort_keys=True),
                )
                sess.add(m)
                await sess.commit()

    async def load_all(self) -> List[DownloadedModel]:
        limit = 100
        offset = 0

        all_models = []
        async with db.session_scope() as sess:
            while True:
                q = (
                    sa.select(db_models.DownloadModel)
                    .order_by(db_models.DownloadModel.id)
                    .limit(limit)
                    .offset(offset)
                )
                models = list((await sess.scalars(q)).all())
                all_models.extend(models)
                if len(models) < limit:
                    break
                offset += len(models)

        return [
            DownloadedModel(
                task_type=model.task_type,
                model_file=ModelFileEntry(
                    source_type=model.source_type,
                    repository=model.repository,
                    revision=model.revision,
                    format=model.format,
                    format_kwargs=json.loads(model.format_kwargs),
                ),
            )
            for model in all_models
        ]
