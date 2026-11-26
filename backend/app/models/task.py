"""测试任务数据模型"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String

from ..database import Base


class Task(Base):
    """测试任务"""

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, comment="任务名称")
    status = Column(String(50), default="pending", comment="pending/running/completed/failed")
    config = Column(JSON, comment="任务配置(JSON): game_name/max_steps/scenarios/mode")
    total_steps = Column(Integer, default=0, comment="总测试步骤数")
    completed_steps = Column(Integer, default=0, comment="已完成步骤数")
    bug_count = Column(Integer, default=0, comment="发现的Bug数量")
    created_at = Column(DateTime, default=datetime.now)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "config": self.config or {},
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "bug_count": self.bug_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, name={self.name}, status={self.status})>"
