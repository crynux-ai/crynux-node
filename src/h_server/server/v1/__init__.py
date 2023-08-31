from fastapi import APIRouter

from .task import router as task_router

router = APIRouter()
router.include_router(task_router, prefix="/task")
