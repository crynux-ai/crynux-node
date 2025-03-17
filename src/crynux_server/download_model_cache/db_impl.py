from hashlib import sha256
from typing import List

import sqlalchemy as sa

import crynux_server.db.models as db_models
from crynux_server import db
from crynux_server.models import DownloadedModel, ModelConfig

from .abc import DownloadModelCache


class DbDownloadModelCache(DownloadModelCache):
    async def save(self, model: DownloadedModel):
        async with db.session_scope() as sess:
            model_id = model.model.to_model_id()
            model_id_hash = sha256(model_id.encode("utf-8")).hexdigest()

            q = sa.select(db_models.DownloadModel).where(
                db_models.DownloadModel.model_id_hash == model_id_hash
            )
            m = (await sess.scalars(q)).one_or_none()
            if m is None:
                m = db_models.DownloadModel(
                    model_id_hash=model_id_hash,
                    task_type=model.task_type,
                    model_name=model.model.id,
                    model_type=model.model.type,
                    variant=model.model.variant,
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
                model=ModelConfig(
                    id=model.model_name,
                    type=model.model_type,
                    variant=model.variant,
                ),
            )
            for model in all_models
        ]
