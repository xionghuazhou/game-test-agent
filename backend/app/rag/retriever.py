"""RAG 检索器：知识库检索（零依赖轻量实现，ChromaDB 可选增强）

实现要点：
- 默认使用内置的 TF-IDF + 字符 bigram 混合评分检索，零模型下载、离线可用
- 若 chromadb 可用则自动切换到向量检索（语义召回更好）
"""
import logging
import math
import re
from collections import Counter
from typing import Optional

from sqlalchemy.orm import Session

from ..config import settings
from ..models.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

_STOP = set("的了和是与不在为一个这那之以及对于从被把将会啊吧呢吗的非常进行可以需要如果那么就是".split())


def _tokenize(text: str) -> list[str]:
    """轻量中文分词：按标点/空白切词 + 英文单词 + 中文 bigram"""
    tokens: list[str] = []
    for seg in re.split(r"[\s，。！？；：、\n\r\t,.!?;:]+", text.lower()):
        if not seg:
            continue
        # 英文/数字串
        for m in re.finditer(r"[a-z0-9_]+", seg):
            tokens.append(m.group(0))
        # 中文：去停用词后逐字 + bigram
        han = re.sub(r"[^一-龥]", "", seg)
        han = "".join(ch for ch in han if ch not in _STOP)
        tokens.extend(han)
        tokens.extend(han[i : i + 2] for i in range(len(han) - 1))
    return [t for t in tokens if t]


class RAGRetriever:
    """知识库检索器"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._chroma: Optional[object] = None
        self._chroma_checked = False

    # ---------- 公共接口 ----------
    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """检索最相关的知识条目，返回 [{title, content, category, source, score}]"""
        rows = self.db.query(KnowledgeBase).all()
        if not rows:
            return []
        if self._try_chroma(rows):
            try:
                return self._chroma_search(query, top_k)
            except Exception as e:  # noqa: BLE001
                logger.warning("Chroma 检索失败，降级为本地检索: %s", e)
        return self._local_search(query, rows, top_k)

    def add_document(self, title: str, content: str, category: str = "doc",
                     source: str = "manual", tags: str = "") -> KnowledgeBase:
        """新增知识条目（同时写入 Chroma（如可用））"""
        kb = KnowledgeBase(title=title, content=content, category=category, source=source, tags=tags)
        self.db.add(kb)
        self.db.commit()
        self.db.refresh(kb)
        if self._try_chroma([kb]):
            try:
                self._chroma_add(kb)
            except Exception as e:  # noqa: BLE001
                logger.warning("Chroma 写入失败(已存SQLite): %s", e)
        return kb

    # ---------- 本地 TF-IDF + bigram 检索 ----------
    def _local_search(self, query: str, rows: list[KnowledgeBase], top_k: int) -> list[dict]:
        q_tokens = [t for t in _tokenize(query) if t]
        if not q_tokens:
            return []
        # 文档频率
        docs_tokens = [_tokenize((r.title or "") + " " + (r.content or "")) for r in rows]
        df: Counter = Counter()
        for toks in docs_tokens:
            df.update(set(toks))
        n_docs = len(rows)
        scored = []
        for r, toks in zip(rows, docs_tokens):
            if not toks:
                continue
            tf = Counter(toks)
            score = 0.0
            for t in q_tokens:
                if t in tf:
                    score += tf[t] * math.log(1 + n_docs / (1 + df.get(t, 0)))
            # 标题命中加权
            title_tokens = set(_tokenize(r.title or ""))
            score += 2.0 * len(title_tokens & set(q_tokens))
            if score > 0:
                scored.append((score, r))
        scored.sort(key=lambda x: -x[0])
        max_score = scored[0][0] if scored else 1.0
        return [
            {
                "title": r.title,
                "content": (r.content or "")[:500],
                "category": r.category,
                "source": r.source,
                "score": round(s / max_score, 3),
            }
            for s, r in scored[:top_k]
        ]

    # ---------- Chroma 可选增强 ----------
    def _try_chroma(self, rows: list[KnowledgeBase]) -> bool:
        if self._chroma_checked:
            return self._chroma is not None
        self._chroma_checked = True
        try:
            import chromadb  # noqa: PLC0415 - 可选依赖

            client = chromadb.PersistentClient(path=settings.SCREENSHOT_DIR.replace("screenshots", "chroma"))
            self._chroma = client.get_or_create_collection("knowledge_base")
            # 同步缺失条目
            existing = set(self._chroma.get()["ids"] or [])
            for r in rows:
                if str(r.id) not in existing:
                    self._chroma_add(r)
            logger.info("RAG: 已启用 ChromaDB 向量检索")
            return True
        except Exception as e:  # noqa: BLE001
            logger.info("RAG: ChromaDB 不可用(%s)，使用内置轻量检索", e.__class__.__name__)
            self._chroma = None
            return False

    def _chroma_add(self, kb: KnowledgeBase) -> None:
        self._chroma.add(
            ids=[str(kb.id)],
            documents=[f"{kb.title}\n{kb.content}"],
            metadatas=[{"title": kb.title, "category": kb.category or "", "source": kb.source or ""}],
        )

    def _chroma_search(self, query: str, top_k: int) -> list[dict]:
        res = self._chroma.query(query_texts=[query], n_results=min(top_k, self._chroma.count() or 1))
        out = []
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        for doc, meta, dist in zip(docs, metas, dists):
            title = meta.get("title", "")
            content = doc[len(title):].strip() if doc.startswith(title) else doc
            out.append({
                "title": title,
                "content": content[:500],
                "category": meta.get("category", ""),
                "source": meta.get("source", ""),
                "score": round(1.0 - float(dist), 3),
            })
        return out
