"""测试日志数据模型"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from ..database import Base


class TestLog(Base):
    """测试执行日志"""

    __tablename__ = "test_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), index=True, comment="关联任务ID")

    step = Column(Integer, default=0, comment="步骤序号")
    phase = Column(String(50), default="execute", comment="阶段: plan/execute/analyze/report")
    action = Column(String(200), comment="执行的动作")
    result = Column(String(50), comment="success/failed/error/bug_found")
    details = Column(Text, comment="详细信息(JSON)")
    timestamp = Column(DateTime, default=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "step": self.step,
            "phase": self.phase,
            "action": self.action,
            "result": self.result,
            "details": self.details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
