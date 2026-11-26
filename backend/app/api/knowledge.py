"""知识库 API（RAG）"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.knowledge_base import KnowledgeBase
from ..rag.retriever import RAGRetriever

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class KnowledgeCreate(BaseModel):
    title: str
    content: str
    category: str = "doc"
    source: str = "manual"
    tags: str = ""


@router.get("")
def list_knowledge(db: Session = Depends(get_db)):
    rows = db.query(KnowledgeBase).order_by(KnowledgeBase.id.desc()).limit(100).all()
    return [k.to_dict() for k in rows]


@router.post("")
def add_knowledge(body: KnowledgeCreate, db: Session = Depends(get_db)):
    kb = RAGRetriever(db).add_document(body.title, body.content, body.category, body.source, body.tags)
    return kb.to_dict()


@router.get("/search")
def search(q: str, top_k: int = 3, db: Session = Depends(get_db)):
    return RAGRetriever(db).search(q, top_k)
