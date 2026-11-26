"""FastAPI 应用入口：API 路由 + WebSocket + 静态面板托管"""
import faulthandler
import logging
import sys
from pathlib import Path

# 崩溃时打印全部线程堆栈（排查线程问题）
faulthandler.enable(file=sys.__stderr__)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import bugs, knowledge, tasks, websocket
from app.config import settings
from app.database import init_db

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="游戏测试Agent", version="1.0.0", description="基于 LLM 的智能游戏测试 Agent 系统")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    logger.info("数据库已初始化 | LLM=%s @ %s | 游戏模式=%s",
                settings.LLM_MODEL, settings.LLM_BASE_URL, settings.GAME_MODE)


# API 路由
app.include_router(tasks.router)
app.include_router(bugs.router)
app.include_router(knowledge.router)
app.include_router(websocket.router)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm_model": settings.LLM_MODEL,
        "llm_base_url": settings.LLM_BASE_URL,
        "game_mode": settings.GAME_MODE,
        "web_search": settings.WEB_SEARCH_ENABLED,
    }


# 静态面板
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 截图与测试产物（data/screenshots 等）
DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)
app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
