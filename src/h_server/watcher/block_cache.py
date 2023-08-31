from abc import ABC, abstractmethod

import sqlalchemy as sa

from h_server import db
from h_server.db import models as db_models


class BlockNumberCache(ABC):
    @abstractmethod
    async def get(self) -> int:
        ...

    @abstractmethod
    async def set(self, block_number: int):
        ...


class MemoryBlockNumberCache(BlockNumberCache):
    def __init__(self) -> None:
        self._number = 0

    async def get(self) -> int:
        return self._number

    async def set(self, block_number: int):
        self._number = block_number


class DbBlockNumberCache(BlockNumberCache):
    async def get(self) -> int:
        async with db.session_scope() as sess:
            q = sa.select(db_models.BlockNumber).where(db_models.BlockNumber.id == 1)
            block = (await sess.scalars(q)).one_or_none()
            if block is None:
                return 0
            else:
                return block.number

    async def set(self, block_number: int):
        async with db.session_scope() as sess:
            q = sa.select(db_models.BlockNumber).where(db_models.BlockNumber.id == 1)
            block = (await sess.scalars(q)).one_or_none()
            if block is None:
                block = db_models.BlockNumber(number=block_number)
                sess.add(block)
            else:
                block.number = block_number
            await sess.commit()
