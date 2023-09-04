from fastapi import APIRouter

from .task import router as task_router

router = APIRouter(prefix="/v1")
router.include_router(task_router)
