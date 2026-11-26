"""屏幕捕获模块"""
import time
from pathlib import Path

from ..config import settings


class ScreenCapture:
    """截图工具（全屏或指定区域）"""

    def capture(self, prefix: str = "screenshot", region: tuple | None = None) -> str:
        import pyautogui  # noqa: PLC0415 - 仅真实模式使用

        path = Path(settings.SCREENSHOT_DIR) / f"{prefix}_{int(time.time() * 1000)}.png"
        img = pyautogui.screenshot(region=region) if region else pyautogui.screenshot()
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path)
        return str(path)
