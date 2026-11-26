"""主控 Agent：根据任务配置规划测试场景与动作序列（LLM 驱动，模板兜底）"""
import logging

from ..llm import LLMClient

logger = logging.getLogger(__name__)

PLAN_SYSTEM = """你是一位资深游戏测试专家（QA Agent）。你会得到一个游戏的简要描述，请规划一条能覆盖核心玩法路径、
并尽量触达边界条件与异常情况的测试动作序列。

要求：
1. 输出 JSON：{"scenarios": [{"name": "场景名", "steps": ["click:元素名", ...]}]}
2. 动作格式必须是以下之一：
   - "click:元素名"    点击指定元素
   - "input:框名:文本" 在输入框输入文本
   - "drag:元素:数值"  拖动滑块到某数值
   - "wait:秒数"       等待若干秒
3. 步数总数控制在 {max_steps} 步以内；优先覆盖：主流程一遍 + 边界操作（重复点击、极端数值、反复进出场景）
4. 只使用游戏描述里出现过的元素名（或明显合理的通用按钮名），不要编造不存在的复杂交互。
"""

FALLBACK_PLAN = {
    "scenarios": [
        {"name": "登录主流程", "steps": ["click:登录按钮", "wait:1", "click:开始游戏"]},
        {"name": "战斗循环", "steps": ["click:攻击", "click:技能", "click:攻击", "click:攻击", "click:攻击"]},
        {"name": "背包与装备边界", "steps": ["click:返回", "click:背包", "click:装备物品", "click:装备物品", "click:装备物品", "click:返回"]},
        {"name": "设置边界", "steps": ["click:设置", "drag:音量滑块:0", "drag:音量滑块:0", "click:返回"]},
    ]
}


class MasterAgent:
    """主控 Agent：负责规划"""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def plan(self, game_name: str, game_desc: str, max_steps: int, known_scenes: list[str] | None = None) -> dict:
        """生成测试计划：{scenarios: [{name, steps: []}]}；LLM 失败时用兜底模板"""
        scene_hint = "、".join(known_scenes) if known_scenes else "登录、主菜单、战斗、背包、设置"
        prompt = (
            f"游戏名称：{game_name or 'DemoGame 模拟RPG'}\n"
            f"游戏描述：{game_desc or '一款RPG游戏，包含登录、主菜单、战斗、背包、设置等场景。'}\n"
            f"已知场景：{scene_hint}\n"
            f"请规划测试动作序列。总步数不超过 {max_steps}。"
        )
        try:
            raw = self.llm.chat(
                [
                    {"role": "system", "content": PLAN_SYSTEM.format(max_steps=max_steps)},
                    {"role": "user", "content": prompt},
                ],
                json_mode=True,
            )
            data = LLMClient.extract_json(raw)
            scenarios = data.get("scenarios") if isinstance(data, dict) else None
            if not scenarios:
                raise ValueError(f"缺少 scenarios, 模型输出键: {list(data) if isinstance(data, dict) else type(data)}")
            steps_all = []
            clean = []
            for sc in scenarios:
                steps = [str(s) for s in sc.get("steps", []) if str(s).strip()]
                clean.append({"name": str(sc.get("name", "场景"))[:50], "steps": steps})
                steps_all.extend(steps)
            # 截断到 max_steps
            total = 0
            final = []
            for sc in clean:
                if total >= max_steps:
                    break
                room = max_steps - total
                sc["steps"] = sc["steps"][:room]
                total += len(sc["steps"])
                if sc["steps"]:
                    final.append(sc)
            logger.info("主控Agent规划完成：%d 个场景，共 %d 步", len(final), sum(len(s["steps"]) for s in final))
            return {"scenarios": final}
        except Exception as e:  # noqa: BLE001
            logger.warning("主控Agent LLM规划失败，使用兜底计划: %s | 原始输出: %s", e, raw[:300] if 'raw' in dir() else 'N/A')
            fallback = {"scenarios": [dict(s) for s in FALLBACK_PLAN["scenarios"]]}
            total = 0
            for sc in fallback["scenarios"]:
                sc["steps"] = sc["steps"][: max(0, max_steps - total)]
                total += len(sc["steps"])
            return fallback
