"""应用全局配置管理（环境变量驱动，OpenAI 兼容 LLM 接口）"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _ENV = Path(__file__).resolve().parent.parent / ".env"
    if _ENV.exists():
        load_dotenv(_ENV, override=False)
except ImportError:
    # 无 python-dotenv 时手工解析 .env
    _ENV = Path(__file__).resolve().parent.parent / ".env"
    if _ENV.exists():
        for line in _ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


class Settings:
    """应用全局配置（环境变量优先于默认值）"""

    def __init__(self) -> None:
        # LLM（OpenAI 兼容协议，SenseNova 中转站）
        self.LLM_API_KEY: str = _get("LLM_API_KEY")
        self.LLM_BASE_URL: str = _get("LLM_BASE_URL", "https://token.sensenova.cn/v1")
        self.LLM_MODEL: str = _get("LLM_MODEL", "deepseek-v4-flash")
        self.LLM_MAX_TOKENS: int = int(_get("LLM_MAX_TOKENS", "4096"))

        # 数据库
        self.DATABASE_URL: str = _get("DATABASE_URL", "sqlite:///./data/game_test.db")

        # 应用
        self.APP_HOST: str = _get("APP_HOST", "127.0.0.1")
        self.APP_PORT: int = int(_get("APP_PORT", "8000"))
        self.DEBUG: bool = _get("DEBUG", "true").lower() in ("1", "true", "yes")
        self.LOG_LEVEL: str = _get("LOG_LEVEL", "INFO").upper()

        # 游戏自动化
        self.GAME_MODE: str = _get("GAME_MODE", "demo")  # demo | window
        self.GAME_WINDOW_TITLE: str = _get("GAME_WINDOW_TITLE", "游戏窗口名称")
        self.SCREENSHOT_DIR: str = _get("SCREENSHOT_DIR", "./data/screenshots")

        # Agent 行为
        self.MAX_STEPS: int = int(_get("MAX_STEPS", "12"))
        self.WEB_SEARCH_ENABLED: bool = _get("WEB_SEARCH_ENABLED", "true").lower() in ("1", "true", "yes")
        self.WEB_SEARCH_MAX_RESULTS: int = int(_get("WEB_SEARCH_MAX_RESULTS", "4"))

        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        Path(self.SCREENSHOT_DIR).mkdir(parents=True, exist_ok=True)
        Path("data").mkdir(parents=True, exist_ok=True)


settings = Settings()
