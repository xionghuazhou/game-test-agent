"""游戏状态与动作的数据结构"""
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class GameElement:
    """可交互元素"""
    name: str            # 元素名称，如 "开始游戏" "攻击" "背包"
    x: int               # 屏幕坐标
    y: int
    enabled: bool = True # 是否可交互

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GameState:
    """游戏当前状态快照（供分析 Agent 使用）"""
    scene: str = "login"                        # 当前场景: login/main_menu/battle/inventory/settings/game_over
    elements: list[GameElement] = field(default_factory=list)
    indicators: dict = field(default_factory=dict)   # 数值指标: hp/mp/score/fps/enemy_count...
    screenshot_path: str = ""                   # 截图文件路径
    screen_text: str = ""                       # 画面文本概述(供 LLM "看")
    last_action: str = ""                       # 最近一次执行的动作
    last_action_result: str = ""                # success/failed/no_response
    changed: bool = False                       # 本步画面是否发生变化

    def to_dict(self) -> dict:
        return {
            "scene": self.scene,
            "elements": [e.to_dict() for e in self.elements],
            "indicators": self.indicators,
            "screenshot_path": self.screenshot_path,
            "screen_text": self.screen_text,
            "last_action": self.last_action,
            "last_action_result": self.last_action_result,
            "changed": self.changed,
        }

    def summary(self) -> str:
        """给 LLM 看的文本摘要"""
        elems = "、".join(f"{e.name}({e.x},{e.y})" + ("" if e.enabled else "[灰]") for e in self.elements)
        inds = "、".join(f"{k}={v}" for k, v in self.indicators.items())
        return f"场景: {self.scene}\n可见元素: {elems or '无'}\n数值指标: {inds or '无'}\n画面文本: {self.screen_text}"
