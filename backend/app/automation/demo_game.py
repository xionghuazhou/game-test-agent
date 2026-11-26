"""内置模拟游戏：一个带预埋 BUG 的类 RPG 状态机，用于 demo 模式跑通全流程

预埋 Bug（供 Agent 发现，验证检测能力）：
1. inventory 场景：点击"装备物品"连续两次后，画面无响应（no_response bug, ui 类）
2. battle 场景：连续战斗 4 次后 HP 会出现负数（-3，logic 越界 bug）
3. settings 场景：音量滑块拖到 0 后显示 "NaN%"（ui 显示 bug）
"""
import random
import time
from pathlib import Path

from PIL import Image, ImageDraw

from .game_state import GameElement, GameState
from ..config import settings


class DemoGame:
    """模拟游戏状态机"""

    SCENES: dict[str, list[tuple]] = {
        "login": [("账号输入框", 640, 300), ("密码输入框", 640, 360), ("登录按钮", 640, 430)],
        "main_menu": [("开始游戏", 640, 260), ("背包", 480, 380), ("设置", 800, 380), ("商城", 640, 460)],
        "battle": [("攻击", 400, 600), ("技能", 640, 600), ("逃跑", 880, 600)],
        "inventory": [("装备物品", 500, 400), ("使用药水", 700, 400), ("丢弃", 600, 520), ("返回", 640, 650)],
        "settings": [("音量滑块", 640, 300), ("画质选择", 640, 400), ("保存设置", 640, 550), ("返回", 640, 650)],
        "game_over": [("重新开始", 640, 400), ("返回主菜单", 640, 500)],
    }

    def __init__(self) -> None:
        self.state = GameState(scene="login")
        self._equip_clicks = 0     # 装备点击次数(触发 bug1)
        self._battle_rounds = 0    # 战斗轮数(触发 bug2)
        self._volume_value = 50    # 音量值(触发 bug3)
        self._volume_min = False
        self._hp = 100
        self._score = 0
        self._render()

    # ---------------- 对外接口 ----------------
    @property
    def state(self) -> GameState:
        return self._state

    @state.setter
    def state(self, v: GameState) -> None:
        self._state = v

    def apply_action(self, action: str, x: int = 0, y: int = 0) -> GameState:
        """执行一次点击/输入动作，推进状态机。动作格式: click:元素名 / drag:音量滑块:0 / wait:1"""
        before_scene = self._state.scene
        before_ind = dict(self._state.indicators)
        action = action.strip()
        no_response = False

        if action.startswith("click:"):
            target = action.split(":", 1)[1].strip()
            no_response = self._click(target)
        elif action.startswith("drag:"):
            # drag:音量滑块:值
            parts = action.split(":")
            no_response = self._drag(parts[1].strip(), int(parts[2]) if len(parts) > 2 else 0)
        elif action.startswith("wait:"):
            time.sleep(min(float(action.split(":")[1] or 0.5), 2.0))

        changed = (self._state.scene != before_scene) or (self._state.indicators != before_ind)
        self._state.last_action = action
        self._state.last_action_result = "no_response" if no_response else ("success" if changed else "success_no_change")
        self._state.changed = changed
        self._render()
        return self._state

    # ---------------- 内部逻辑 ----------------
    def _click(self, target: str) -> bool:
        """返回 True 表示发生了 no_response bug"""
        scene = self._state.scene

        if scene == "login":
            if "登录" in target:
                self._state.scene = "main_menu"
                self._state.indicators = {"player_level": 1, "fps": 60}
            return False

        if scene == "main_menu":
            if "开始游戏" in target:
                self._state.scene = "battle"
                self._hp = 100
                self._battle_rounds = 0
                self._state.indicators = {"hp": self._hp, "score": self._score, "fps": 60, "enemy_count": 3}
            elif "背包" in target:
                self._state.scene = "inventory"
                self._state.indicators = {"item_count": 12, "gold": 1500, "fps": 60}
            elif "设置" in target:
                self._state.scene = "settings"
                self._state.indicators = {"volume": self._volume_value, "quality": "高", "fps": 60}
            return False

        if scene == "battle":
            self._battle_rounds += 1
            self._hp = max(0, self._hp - random.randint(5, 15))
            self._score += random.randint(10, 50)
            # 预埋 Bug2: 第 4 轮起 HP 越界为负数
            if self._battle_rounds >= 4:
                self._hp = -3
            self._state.indicators = {"hp": self._hp, "score": self._score, "fps": random.randint(55, 61),
                                      "enemy_count": max(0, 3 - self._battle_rounds // 2)}
            if self._hp == 0:
                self._state.scene = "game_over"
                self._state.indicators["result"] = "defeat"
            return False

        if scene == "inventory":
            if "装备" in target:
                self._equip_clicks += 1
                # 预埋 Bug1: 第二次点击后无响应
                if self._equip_clicks >= 2:
                    return True  # no_response
                self._state.indicators["item_count"] = max(0, self._state.indicators.get("item_count", 0) - 1)
            elif "药水" in target:
                self._state.indicators["item_count"] = max(0, self._state.indicators.get("item_count", 0) - 1)
                self._state.indicators["hp_potion"] = self._state.indicators.get("hp_potion", 0) + 1
            elif "返回" in target:
                self._state.scene = "main_menu"
                self._state.indicators = {"player_level": 1, "fps": 60}
            return False

        if scene == "settings":
            if "音量" in target:
                # 预埋 Bug3: 音量滑到 0 后显示 NaN
                self._volume_value = 0 if self._volume_value <= 0 else self._volume_value - 50
                if self._volume_value <= 0:
                    self._volume_min = True
                self._state.indicators["volume_display"] = "NaN%" if self._volume_min else f"{max(0, self._volume_value)}%"
                self._state.indicators["volume_raw"] = max(0, self._volume_value)
            elif "保存" in target:
                self._state.indicators["saved"] = True
            elif "返回" in target:
                self._state.scene = "main_menu"
                self._state.indicators = {"player_level": 1, "fps": 60}
            return False

        if scene == "game_over":
            if "重新开始" in target:
                self._state.scene = "battle"
                self._hp = 100
                self._battle_rounds = 0
                self._state.indicators = {"hp": 100, "score": self._score, "fps": 60, "enemy_count": 3}
            elif "主菜单" in target:
                self._state.scene = "main_menu"
                self._state.indicators = {"player_level": 1, "fps": 60}
            return False

        return False

    def _drag(self, target: str, value: int) -> bool:
        if "音量" in target:
            self._volume_value = value
            if value <= 0:
                self._volume_min = True
            self._state.indicators["volume_display"] = "NaN%" if self._volume_min else f"{max(0, value)}%"
            self._state.indicators["volume_raw"] = max(0, value)
            return False
        return False

    def _render(self) -> None:
        """渲染模拟画面（截图）+ 元素列表 + 画面文本"""
        scene = self._state.scene
        self._state.elements = [GameElement(n, x, y) for (n, x, y) in self.SCENES.get(scene, [])]
        self._state.screen_text = self._scene_text()
        self._state.screenshot_path = self._save_screenshot()

    def _scene_text(self) -> str:
        s = self._state
        ind = dict(s.indicators)
        if s.scene == "login":
            return "登录界面：账号输入框、密码输入框、登录按钮"
        if s.scene == "main_menu":
            return "游戏主菜单：开始游戏、背包、设置、商城"
        if s.scene == "battle":
            hp = ind.get("hp", 100)
            return f"战斗场景：HP {hp}，敌人 {ind.get('enemy_count', 0)} 个，得分 {ind.get('score', 0)}，帧率 {ind.get('fps')}"
        if s.scene == "inventory":
            vol = ind.get("volume_display")
            return f"背包界面：持有物品 {ind.get('item_count', 0)} 件，金币 {ind.get('gold', 0)}" + (f"，药水 {ind.get('hp_potion', 0)} 瓶" if ind.get("hp_potion") else "")
        if s.scene == "settings":
            return f"设置界面：音量 {ind.get('volume_display', ind.get('volume', 50))}，画质 {ind.get('quality', '高')}"
        if s.scene == "game_over":
            return f"游戏结束：{ind.get('result', 'defeat')}，最终得分 {ind.get('score', 0)}"
        return "未知场景"

    def _save_screenshot(self) -> str:
        """渲染一张模拟游戏截图 PNG"""
        s = self._state
        path = Path(settings.SCREENSHOT_DIR) / f"step_{int(time.time()*1000)}.png"
        img = Image.new("RGB", (1280, 720), (24, 26, 38))
        dr = ImageDraw.Draw(img)
        colors = {"login": (40, 60, 100), "main_menu": (60, 40, 90), "battle": (90, 30, 30),
                  "inventory": (40, 70, 50), "settings": (50, 55, 65), "game_over": (20, 20, 20)}
        dr.rectangle([0, 0, 1280, 80], fill=colors.get(s.scene, (40, 40, 60)))
        dr.text((20, 30), f"DemoGame - {s.scene.upper()}  [{s.last_action_result}]", fill=(230, 230, 230))
        for e in s.elements:
            dr.rounded_rectangle([e.x - 90, e.y - 24, e.x + 90, e.y + 24], 8,
                                 fill=(70, 90, 130) if e.enabled else (60, 60, 60))
            dr.text((e.x - len(e.name.encode('gbk', errors='ignore')) * 5, e.y - 7), e.name, fill=(255, 255, 255))
        # 指标条
        y = 110
        for k, v in s.indicators.items():
            dr.text((20, y), f"{k}: {v}", fill=(140, 220, 160))
            y += 22
        if s.scene == "battle" and "hp" in s.indicators:
            hp = max(0, s.indicators["hp"])
            dr.rectangle([440, 140, 840, 160], fill=(60, 20, 20))
            dr.rectangle([440, 140, 440 + int(400 * hp / 100), 160], fill=(200, 60, 60))
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path)
        return str(path)
