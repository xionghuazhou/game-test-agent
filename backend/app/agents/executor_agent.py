"""执行 Agent：将规划的动作映射到游戏控制器实际执行（demo 模拟 / 真实窗口）"""
import logging
import re

from ..automation.game_controller import GameController
from ..automation.game_state import GameState

logger = logging.getLogger(__name__)

# 动作白名单格式
_ACTION_RE = re.compile(r"^(click|input|drag|wait):.+")


class ExecutorAgent:
    """执行 Agent"""

    def __init__(self, controller: GameController) -> None:
        self.controller = controller

    def resolve_action(self, planned: str, state: GameState) -> tuple[str, int, int]:
        """把规划的动作解析为控制器动作：元素名 → 坐标（demo 用元素表，window 用比例坐标）"""
        action = planned.strip()
        if not _ACTION_RE.match(action):
            action = f"click:{action}"
        kind, _, rest = action.partition(":")
        if kind == "click":
            target = rest.strip()
            # demo: 从元素表找坐标
            for e in state.elements:
                if e.name == target or target in e.name:
                    return f"click:{e.name}", e.x, e.y
            # 模糊匹配（LLM 可能写"登录"而元素叫"登录按钮"）
            for e in state.elements:
                if any(ch in e.name for ch in target if ch):
                    return f"click:{e.name}", e.x, e.y
            return f"click:{target}", 0, 0
        if kind == "drag":
            parts = rest.split(":")
            name = parts[0].strip()
            val = int(parts[1]) if len(parts) > 1 and parts[1].strip().lstrip("-").isdigit() else 0
            return f"drag:{name}:{val}", 0, 0
        return action, 0, 0

    def execute(self, planned: str, state: GameState) -> GameState:
        """执行一步动作并返回新的游戏状态"""
        action, x, y = self.resolve_action(planned, state)
        logger.info("执行Agent: %s", action)
        new_state = self.controller.apply_action(action, x, y)
        return new_state
