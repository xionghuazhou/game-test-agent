"""任务管理 API"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.task_service import TaskService

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskCreate(BaseModel):
    name: str
    config: dict = {}


@router.get("")
def list_tasks(db: Session = Depends(get_db)):
    return [t.to_dict() for t in TaskService(db).list_tasks()]


@router.post("")
def create_task(body: TaskCreate, db: Session = Depends(get_db)):
    if not body.name.strip():
        raise HTTPException(400, "任务名称不能为空")
    task = TaskService(db).create_task(body.name.strip(), body.config)
    return task.to_dict()


@router.get("/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = TaskService(db).get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return task.to_dict()


@router.post("/{task_id}/start")
def start_task(task_id: int, db: Session = Depends(get_db)):
    try:
        task = TaskService(db).start_task(task_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return task.to_dict()


@router.delete("/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    ok = TaskService(db).delete_task(task_id)
    if not ok:
        raise HTTPException(404, "任务不存在")
    return {"message": "任务已删除", "task_id": task_id}


@router.get("/{task_id}/logs")
def task_logs(task_id: int, db: Session = Depends(get_db)):
    return [l.to_dict() for l in TaskService(db).list_logs(task_id)]
