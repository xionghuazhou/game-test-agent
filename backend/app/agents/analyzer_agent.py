"""分析 Agent：LLM 分析游戏状态判断异常；结合 RAG 知识库与联网搜索增强判定（本系统核心）"""
import logging

from ..llm import LLMClient
from ..rag.retriever import RAGRetriever
from ..tools.web_search import web_search

logger = logging.getLogger(__name__)

ANALYZE_SYSTEM = """你是资深游戏 QA 分析专家。你将收到一次测试步骤的执行结果，包括：
- 游戏当前状态摘要（场景、可见元素、数值指标、画面文本）
- 最近若干步的历史状态
- 从历史 Bug 知识库检索到的相似案例
- （可能）互联网搜索到的相关资料

请判断本步骤是否暴露了游戏 BUG。判断标准：
1. 数值异常：HP/金币/得分出现负数、NaN、越界、不符合逻辑的大幅跳变
2. 交互异常：点击元素后画面长时间无响应(last_action_result=no_response)、元素点击后状态与预期不符
3. 显示异常：界面文本出现 NaN%、undefined、乱码、错位描述
4. 一致性异常：同一操作多次执行结果不一致（且非随机设计）

注意：
- 正常的数值下降（如战斗扣血）不是 BUG
- 场景正常切换、正常随机浮动不是 BUG
- 必须结合知识库与搜索证据给出判定，不要臆测

输出 JSON：
{
  "is_bug": true/false,
  "severity": "critical/high/medium/low",   // is_bug 时给出
  "category": "ui/logic/performance/crash", // is_bug 时给出
  "title": "简短Bug标题(50字内)",
  "description": "详细描述(120字内)：现象+数据",
  "expected": "预期行为",
  "actual": "实际行为",
  "evidence": "判定依据：引用知识库案例或搜索结果的关键内容；若无外部证据写'基于状态数据判定'"
}
"""


class AnalyzerAgent:
    """分析 Agent"""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def analyze(
        self,
        game_name: str,
        state_dict: dict,
        history: list[dict],
        step_no: int,
        retriever: RAGRetriever | None = None,
    ) -> dict:
        """分析一步执行结果。返回分析结果 dict（含 is_bug 等）"""
        # 1) RAG 检索相似历史 Bug
        rag_hits: list[dict] = []
        query_parts = [state_dict.get("scene", ""), state_dict.get("last_action", ""),
                       state_dict.get("last_action_result", "")]
        inds = state_dict.get("indicators") or {}
        query_parts += [f"{k}={v}" for k, v in list(inds.items())[:4]]
        query = " ".join(str(x) for x in query_parts if x)
        if retriever is not None:
            try:
                rag_hits = retriever.search(query, top_k=3)
            except Exception as e:  # noqa: BLE001
                logger.warning("RAG 检索失败: %s", e)

        rag_text = "\n".join(
            f"- [{h.get('category','')}] {h.get('title','')}: {h.get('content','')[:150]}" for h in rag_hits
        ) or "（无相似案例）"

        # 2) 判断是否需要联网搜索（无响应/数值异常/显示NaN等可疑信号时才搜，控制开销）
        suspicious = (
            state_dict.get("last_action_result") == "no_response"
            or any(str(v).lower() in ("nan", "none", "undefined", "-3") or (isinstance(v, (int, float)) and v < 0)
                   for v in (state_dict.get("indicators") or {}).values())
        )
        search_text = "（未触发联网搜索）"
        if suspicious and web_search:
            game = game_name or "游戏"
            symptom = ""
            if state_dict.get("last_action_result") == "no_response":
                symptom = f"点击{state_dict.get('last_action','按钮')}后界面无响应"
            else:
                abnormal = [f"{k}={v}" for k, v in (inds or {}).items()
                            if str(v).lower() in ("nan", "undefined") or (isinstance(v, (int, float)) and v < 0)]
                symptom = "数值显示异常 " + "、".join(abnormal) if abnormal else "界面显示异常"
            results = web_search.search(f"{game} {symptom} 常见bug 原因", max_results=3)
            if results:
                search_text = "\n".join(f"- 《{r['title']}》 {r['snippet'][:120]} ({r['url']})" for r in results)
            else:
                search_text = "（联网搜索无结果）"

        # 3) 构造历史摘要
        hist_text = "\n".join(
            f"步骤{h.get('step')}: {h.get('action')} -> {h.get('result')}；状态: {h.get('summary', '')[:120]}"
            for h in history[-5:]
        ) or "（这是第一步）"

        user_prompt = (
            f"游戏名称：{game_name or 'DemoGame 模拟RPG'}\n"
            f"当前步骤：第 {step_no} 步\n"
            f"当前游戏状态：\n{self._state_text(state_dict)}\n\n"
            f"最近历史：\n{hist_text}\n\n"
            f"知识库相似案例：\n{rag_text}\n\n"
            f"联网搜索结果：\n{search_text}\n\n"
            f"请判断本步骤是否暴露 BUG，输出 JSON。"
        )
        try:
            data = self.llm.chat_json(
                [
                    {"role": "system", "content": ANALYZE_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
            )
            data["rag_hits"] = rag_hits
            data["web_search_used"] = suspicious
            return self._normalize(data)
        except Exception as e:  # noqa: BLE001
            logger.error("分析Agent LLM调用失败: %s", e)
            # 明确非法状态必须被规则捕获，LLM 不可用也不能静默漏报
            return self._rule_based_fallback(state_dict, str(e), rag_hits, suspicious)

    @staticmethod
    def _rule_based_fallback(
        state_dict: dict, error: str, rag_hits: list[dict], web_search_used: bool
    ) -> dict:
        """在 LLM 失败时识别无响应、负数和 NaN/undefined 等确定性异常。"""
        import math

        indicators = state_dict.get("indicators") or {}
        negative = {
            k: v for k, v in indicators.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v < 0
        }
        invalid = {
            k: v for k, v in indicators.items()
            if (isinstance(v, float) and math.isnan(v))
            or str(v).lower() in ("nan", "none", "undefined")
        }
        no_response = state_dict.get("last_action_result") == "no_response"
        is_bug = bool(negative or invalid or no_response)
        abnormal = {**negative, **invalid}
        actual = "、".join(f"{k}={v}" for k, v in abnormal.items())
        if no_response:
            actual = actual or "点击后界面无响应"
        return {
            "is_bug": is_bug,
            "severity": "high" if abnormal else ("medium" if is_bug else "low"),
            "category": "logic" if abnormal else "ui",
            "title": (f"数值越界：{actual}（规则兜底判定）" if abnormal
                      else ("点击后界面无响应（规则兜底判定）" if is_bug else "")),
            "description": (f"检测到非法游戏状态：{actual}；LLM分析失败({error})，使用规则兜底"
                            if is_bug else ""),
            "expected": "数值应处于合法范围（HP 等不应小于 0），界面操作应有响应",
            "actual": actual,
            "evidence": "规则兜底：负数、NaN/undefined 或无响应属于明确异常状态",
            "rag_hits": rag_hits,
            "web_search_used": web_search_used,
        }

    @staticmethod
    def _normalize(data: dict) -> dict:
        """规范化模型输出的 severity/category 枚举"""
        sev_map = {"严重": "critical", "高": "high", "中": "medium", "低": "low",
                   "致命": "critical", "紧急": "critical"}
        cat_map = {"数值": "logic", "数值异常": "logic", "逻辑": "logic", "显示": "ui", "界面": "ui",
                   "性能": "performance", "崩溃": "crash", "卡死": "crash", "闪退": "crash",
                   "功能": "logic", "交互": "ui"}
        sev = str(data.get("severity", "medium")).lower().strip()
        data["severity"] = sev if sev in ("critical", "high", "medium", "low") else sev_map.get(sev, "medium")
        cat = str(data.get("category", "ui")).lower().strip()
        data["category"] = cat if cat in ("ui", "logic", "performance", "crash") else cat_map.get(cat, "ui")
        return data

    @staticmethod
    def _state_text(state: dict) -> str:
        elems = "、".join(f"{e.get('name')}" + ("" if e.get("enabled", True) else "[灰色不可点]") for e in state.get("elements", []))
        inds = "、".join(f"{k}={v}" for k, v in (state.get("indicators") or {}).items())
        return (
            f"场景: {state.get('scene')}\n"
            f"最近动作: {state.get('last_action')} -> 结果: {state.get('last_action_result')}\n"
            f"画面是否变化: {state.get('changed')}\n"
            f"可见元素: {elems or '无'}\n"
            f"数值指标: {inds or '无'}\n"
            f"画面文本: {state.get('screen_text', '')}"
        )
