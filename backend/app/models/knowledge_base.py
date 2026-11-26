"""知识库数据模型（RAG 检索用）"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from ..database import Base


class KnowledgeBase(Base):
    """知识库条目"""

    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False, comment="标题")
    content = Column(Text, nullable=False, comment="内容")
    category = Column(String(50), comment="bug/doc/rule")
    source = Column(String(200), comment="来源")
    tags = Column(String(500), comment="标签(逗号分隔)")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "source": self.source,
            "tags": self.tags,
        }
