"""任务业务服务层"""
import logging
import threading
from datetime import datetime

from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..models.bug_report import BugReport
from ..models.task import Task
from ..models.test_log import TestLog
from ..workflow.test_workflow import WorkflowContext, build_workflow

logger = logging.getLogger(__name__)

# task_id -> WebSocket 广播回调（由 api/websocket.py 注册）
_ws_broadcaster = None


def register_broadcaster(fn) -> None:
    """注册 WebSocket 广播函数：fn(task_id, event: dict)"""
    global _ws_broadcaster
    _ws_broadcaster = fn


def _emit(task_id: int, type_: str, data: dict) -> None:
    if _ws_broadcaster:
        try:
            _ws_broadcaster(task_id, {"type": type_, **data})
        except Exception as e:  # noqa: BLE001
            logger.warning("广播失败: %s", e)


def run_task_background(task_id: int) -> threading.Thread:
    """在新线程中执行测试工作流（每任务一次，互不阻塞 API）"""

    def _runner() -> None:
        db: Session = SessionLocal()
        try:
            ctx = WorkflowContext(task_id, db, on_event=lambda t, d: _emit(task_id, t, d))
            app = build_workflow(ctx)
            app.invoke({})
        except Exception as e:  # noqa: BLE001
            logger.exception("任务执行异常")
            task = db.query(Task).get(task_id)
            if task:
                task.status = "failed"
                task.completed_at = datetime.now()
                db.add(TestLog(task_id=task_id, phase="report", action="任务异常终止",
                               result="error", details=str(e)[:1500]))
                db.commit()
            _emit(task_id, "done", {"status": "failed", "error": str(e)})
        finally:
            db.close()

    th = threading.Thread(target=_runner, name=f"task-{task_id}", daemon=True)
    th.start()
    return th


class TaskService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_task(self, name: str, config: dict) -> Task:
        task = Task(
            name=name,
            status="pending",
            config={
                "game_name": (config or {}).get("game_name", "DemoGame 模拟RPG"),
                "game_desc": (config or {}).get("game_desc", ""),
                "max_steps": int((config or {}).get("max_steps") or settings.MAX_STEPS),
                "mode": (config or {}).get("mode") or settings.GAME_MODE,
                "scenes": (config or {}).get("scenes") or ["login", "main_menu", "battle", "inventory", "settings"],
            },
            total_steps=int((config or {}).get("max_steps") or settings.MAX_STEPS),
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def list_tasks(self) -> list[Task]:
        return self.db.query(Task).order_by(Task.id.desc()).all()

    def get_task(self, task_id: int) -> Task | None:
        return self.db.query(Task).get(task_id)

    def start_task(self, task_id: int) -> Task:
        task = self.get_task(task_id)
        if not task:
            raise ValueError("任务不存在")
        if task.status == "running":
            raise ValueError("任务已在运行中")
        task.status = "running"
        self.db.commit()
        run_task_background(task_id)
        return task

    def delete_task(self, task_id: int) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False
        self.db.query(BugReport).filter(BugReport.task_id == task_id).delete()
        self.db.query(TestLog).filter(TestLog.task_id == task_id).delete()
        self.db.delete(task)
        self.db.commit()
        return True

    def list_logs(self, task_id: int) -> list[TestLog]:
        return self.db.query(TestLog).filter(TestLog.task_id == task_id).order_by(TestLog.id).all()

    def list_bugs(self, task_id: int | None = None) -> list[BugReport]:
        q = self.db.query(BugReport).order_by(BugReport.id.desc())
        if task_id:
            q = q.filter(BugReport.task_id == task_id)
        return q.all()
