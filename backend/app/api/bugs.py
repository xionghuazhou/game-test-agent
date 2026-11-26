"""Bug 报告 API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.task_service import TaskService

router = APIRouter(prefix="/api/bugs", tags=["bugs"])


@router.get("")
def list_bugs(task_id: int | None = None, db: Session = Depends(get_db)):
    return [b.to_dict() for b in TaskService(db).list_bugs(task_id)]


@router.get("/{bug_id}")
def get_bug(bug_id: int, db: Session = Depends(get_db)):
    bug = TaskService(db).list_bugs()
    for b in bug:
        if b.id == bug_id:
            return b.to_dict()
    raise HTTPException(404, "Bug不存在")
