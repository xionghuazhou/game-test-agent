"""Bug 报告数据模型"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from ..database import Base


class BugReport(Base):
    """Bug 报告"""

    __tablename__ = "bug_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), comment="关联任务ID")

    title = Column(String(500), nullable=False, comment="Bug标题")
    severity = Column(String(20), default="medium", comment="critical/high/medium/low")
    category = Column(String(50), comment="ui/logic/performance/crash")

    description = Column(Text, comment="详细描述")
    steps = Column(Text, comment="重现步骤(JSON)")
    expected_behavior = Column(Text, comment="预期行为")
    actual_behavior = Column(Text, comment="实际行为")
    evidence = Column(Text, comment="判定依据(Agent分析+搜索+RAG)")

    screenshot_path = Column(String(500), comment="截图路径")
    log_path = Column(String(500), comment="日志路径")

    status = Column(String(20), default="new", comment="new/confirmed/fixed/closed")
    detected_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "title": self.title,
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "steps": self.steps,
            "expected_behavior": self.expected_behavior,
            "actual_behavior": self.actual_behavior,
            "evidence": self.evidence,
            "screenshot_path": self.screenshot_path,
            "status": self.status,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
        }
