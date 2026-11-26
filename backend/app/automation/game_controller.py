"""游戏控制器：统一封装 demo 模拟游戏与真实窗口控制（PyAutoGUI）

真实模式说明：通过 win32 找到 GAME_WINDOW_TITLE 对应窗口 → 置前 → 用 PyAutoGUI 点击/截图。
真实模式下画面信息通过截图+变化检测(ImageChops)得到，元素坐标由规划 Agent 依据窗口尺寸推断。
"""
import logging
import time
from pathlib import Path
from typing import Optional

from ..config import settings
from .game_state import GameElement, GameState

logger = logging.getLogger(__name__)


class GameController:
    """游戏控制器（demo / window 双模式）"""

    def __init__(self, mode: Optional[str] = None, game_name: str = "") -> None:
        self.mode = (mode or settings.GAME_MODE).lower()
        self.game_name = game_name or settings.GAME_WINDOW_TITLE
        self._demo = None
        self._prev_shot: Optional[bytes] = None
        if self.mode == "demo":
            from .demo_game import DemoGame

            self._demo = DemoGame()

    # ---------------- 对外接口 ----------------
    @property
    def is_demo(self) -> bool:
        return self.mode == "demo"

    def get_state(self) -> GameState:
        """获取当前游戏状态快照"""
        if self.is_demo:
            return self._demo.state
        return self._window_state()

    def apply_action(self, action: str, x: int = 0, y: int = 0) -> GameState:
        """执行动作。动作格式: click:元素名 / drag:元素:值 / input:框名:文本 / wait:秒"""
        if self.is_demo:
            return self._demo.apply_action(action, x, y)
        return self._window_action(action, x, y)

    # ---------------- 真实窗口模式 ----------------
    def _find_window_rect(self) -> Optional[tuple]:
        """查找游戏窗口矩形 (left, top, right, bottom)，Windows 优先用 win32"""
        try:
            import win32gui  # noqa: PLC0415

            hwnd = win32gui.FindWindow(None, self.game_name)
            if not hwnd:
                # 模糊匹配窗口标题
                def cb(h, acc):
                    title = win32gui.GetWindowText(h)
                    if self.game_name and self.game_name in title:
                        acc.append(h)
                    return True
                acc: list = []
                win32gui.EnumWindows(cb, acc)
                hwnd = acc[0] if acc else None
            if hwnd:
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.3)
                return win32gui.GetWindowRect(hwnd)
        except Exception as e:  # noqa: BLE001
            logger.warning("win32 查找窗口失败: %s", e)
        return None

    def _window_state(self) -> GameState:
        """真实模式：截取窗口画面，做变化检测；元素列表由调用方(LLM规划)提供"""
        import pyautogui  # noqa: PLC0415

        st = GameState(scene="window", last_action=self._last_action or "")
        rect = self._find_window_rect()
        if rect:
            l, t, r, b = rect
            shot = pyautogui.screenshot(region=(l, t, r - l, b - t))
        else:
            shot = pyautogui.screenshot()
        path = Path(settings.SCREENSHOT_DIR) / f"win_{int(time.time()*1000)}.png"
        shot.save(path)
        st.screenshot_path = str(path)

        # 变化检测：与上一帧比较
        try:
            from PIL import ImageChops

            if self._prev_shot is not None:
                cur = shot.convert("L").resize((160, 90))
                prev_img = self._prev_img
                diff = ImageChops.difference(cur, prev_img)
                bbox = diff.getbbox()
                st.changed = bbox is not None
            self._prev_shot = shot.tobytes()
            from PIL import Image
            self._prev_img = shot.convert("L").resize((160, 90))
        except Exception as e:  # noqa: BLE001
            logger.warning("变化检测失败: %s", e)
        st.last_action_result = "success" if st.changed else "no_response"
        return st

    _last_action: str = ""
    _prev_img = None

    def _window_action(self, action: str, x: int = 0, y: int = 0) -> GameState:
        import pyautogui  # noqa: PLC0415

        self._last_action = action
        rect = self._find_window_rect()
        if action.startswith("click:") and rect:
            l, t, r, b = rect
            pyautogui.click(l + x, t + y)
            time.sleep(0.6)
        elif action.startswith("input:"):
            parts = action.split(":", 2)
            if len(parts) == 3:
                pyautogui.typewrite(parts[2], interval=0.05)
        elif action.startswith("wait:"):
            time.sleep(min(float(action.split(":")[1] or 0.5), 3.0))
        return self._window_state()
