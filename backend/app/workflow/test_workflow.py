"""游戏测试工作流：plan → execute → analyze → (bug?) → next/finish 的 LangGraph 式状态图"""
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from ..agents.analyzer_agent import AnalyzerAgent
from ..agents.executor_agent import ExecutorAgent
from ..agents.master_agent import MasterAgent
from ..automation.game_controller import GameController
from ..config import settings
from ..llm import LLMClient
from ..models.bug_report import BugReport
from ..models.task import Task
from ..models.test_log import TestLog
from ..rag.retriever import RAGRetriever
from .engine import END, START, StateGraph

logger = logging.getLogger(__name__)


class WorkflowContext:
    """运行期上下文：把 DB 会话/回调传入节点"""

    def __init__(self, task_id: int, db: Session, on_event=None) -> None:
        self.task_id = task_id
        self.db = db
        self.on_event = on_event or (lambda type_, data: None)

    def emit(self, type_: str, data: dict) -> None:
        try:
            self.on_event(type_, data)
        except Exception as e:  # noqa: BLE001 - 推送失败不中断测试
            logger.warning("WS 推送失败: %s", e)


def build_workflow(ctx: WorkflowContext):
    """构建测试工作流（每个任务独立编译一份，节点闭包引用 ctx）"""
    llm = LLMClient()
    task = ctx.db.query(Task).get(ctx.task_id)
    cfg = task.config or {}
    game_name = cfg.get("game_name", "")
    game_desc = cfg.get("game_desc", "")
    max_steps = int(cfg.get("max_steps") or settings.MAX_STEPS)
    mode = cfg.get("mode") or settings.GAME_MODE

    controller = GameController(mode=mode, game_name=game_name)
    executor = ExecutorAgent(controller)
    analyzer = AnalyzerAgent(llm)
    master = MasterAgent(llm)
    retriever = RAGRetriever(ctx.db)

    # ---------- 节点 ----------
    def plan_node(state: dict) -> dict:
        ctx.emit("phase", {"phase": "plan", "message": "主控Agent正在规划测试路径…"})
        plan = master.plan(game_name, game_desc, max_steps, known_scenes=cfg.get("scenes"))
        steps = [(sc["name"], s) for sc in plan["scenarios"] for s in sc["steps"]]
        # 持久化计划
        task.total_steps = len(steps)
        task.status = "running"
        task.started_at = datetime.now()
        ctx.db.add(TestLog(task_id=task.id, phase="plan", action="生成测试计划",
                           result="success", details=str(plan)[:2000]))
        ctx.db.commit()
        ctx.emit("plan", {"plan": plan, "total_steps": len(steps)})
        return {"plan": plan, "steps": steps, "step_idx": 0, "history": [], "bugs": 0}

    def execute_node(state: dict) -> dict:
        steps: list = state["steps"]
        idx: int = state["step_idx"]
        if idx >= len(steps):
            return {"done": True}
        scene_name, planned = steps[idx]
        st = controller.get_state() if state["step_idx"] > 0 or controller.is_demo else None
        if state["step_idx"] == 0:
            st = controller.get_state()  # 初始状态
        ctx.emit("phase", {"phase": "execute", "step": idx + 1, "action": planned,
                           "message": f"[{scene_name}] 执行: {planned}"})
        try:
            new_state = executor.execute(planned, st)
        except Exception as e:  # noqa: BLE001
            logger.exception("执行动作失败")
            new_state = st
            new_state.last_action = planned
            new_state.last_action_result = "error"
            new_state.screen_text = f"执行异常: {e}"
        return {"current_state": new_state.to_dict(), "scene_name": scene_name,
                "planned": planned, "step_idx": idx + 1}

    def analyze_node(state: dict) -> dict:
        st: dict = state["current_state"]
        step_no: int = state["step_idx"]
        ctx.emit("phase", {"phase": "analyze", "step": step_no,
                           "message": f"分析Agent正在分析第 {step_no} 步…" + ("（触发联网搜索）" if _suspicious(st) else "")})
        history = state["history"]
        analysis = analyzer.analyze(game_name, st, history, step_no, retriever)

        # 记录日志
        log = TestLog(
            task_id=task.id, step=step_no, phase="execute",
            action=state["planned"], result=st.get("last_action_result", "unknown"),
            details=str({"screen": st.get("screen_text", ""), "indicators": st.get("indicators", {})})[:1500],
        )
        ctx.db.add(log)
        ctx.db.commit()

        summary = st.get("screen_text", "")
        history.append({"step": step_no, "action": state["planned"], "result": st.get("last_action_result"),
                        "summary": summary})
        ctx.emit("step", {
            "step": step_no, "action": state["planned"], "result": st.get("last_action_result"),
            "scene": st.get("scene"), "screen_text": st.get("screen_text"),
            "indicators": st.get("indicators"), "screenshot": st.get("screenshot_path"),
            "is_bug": analysis.get("is_bug", False),
        })

        patch: dict = {"history": history, "last_analysis": analysis,
                       "completed": state.get("completed", 0) + 1}
        if analysis.get("is_bug"):
            # Bug 去重：同一任务内与已有 Bug 高度相似（同根因）时合并证据而不重复入库
            from difflib import SequenceMatcher

            dup = None
            for old in ctx.db.query(BugReport).filter(BugReport.task_id == task.id).all():
                ratio = SequenceMatcher(None, analysis.get("title", ""), old.title or "").ratio()
                desc_ratio = SequenceMatcher(None, analysis.get("description", ""), old.description or "").ratio()
                if ratio > 0.55 or desc_ratio > 0.6:
                    dup = old
                    break
            if dup is not None:
                extra = f"\n[步骤{step_no}复核] {analysis.get('description', '')}"
                dup.evidence = ((dup.evidence or "") + extra)[:2000]
                ctx.db.commit()
                ctx.emit("bug", {"bug": dup.to_dict(), "dedup": True})
                logger.info("Bug 去重：与 #%s 相似，已合并证据", dup.id)
            else:
                bug = BugReport(
                    task_id=task.id,
                    title=analysis.get("title", "未命名Bug")[:500],
                    severity=analysis.get("severity", "medium"),
                    category=analysis.get("category", "ui"),
                    description=analysis.get("description", ""),
                    steps=f"[{state['scene_name']}] {state['planned']}",
                    expected_behavior=analysis.get("expected", ""),
                    actual_behavior=analysis.get("actual", ""),
                    evidence=analysis.get("evidence", ""),
                    screenshot_path=st.get("screenshot_path", ""),
                )
                ctx.db.add(bug)
                task.bug_count = (task.bug_count or 0) + 1
                ctx.db.commit()
                ctx.db.refresh(bug)
                ctx.emit("bug", {"bug": bug.to_dict()})
                patch["bugs"] = state.get("bugs", 0) + 1
        return patch

    def route_after_analyze(state: dict) -> str:
        steps = state["steps"]
        idx = state["step_idx"]
        if state.get("done") or idx >= len(steps):
            return "finish"
        if idx >= max_steps:
            return "finish"
        return "continue"

    def finish_node(state: dict) -> dict:
        task.status = "completed"
        task.completed_steps = state.get("completed", 0)
        task.completed_at = datetime.now()
        ctx.db.add(TestLog(task_id=task.id, phase="report", action="测试完成",
                           result="success",
                           details=f"共{task.completed_steps}步，发现{task.bug_count}个Bug"))
        ctx.db.commit()
        ctx.emit("done", {"status": "completed", "total": task.completed_steps,
                          "bugs": task.bug_count})
        return {"finished": True}

    # ---------- 组图（LangGraph 风格） ----------
    g = StateGraph()
    g.add_node("plan", plan_node)
    g.add_node("execute", execute_node)
    g.add_node("analyze", analyze_node)
    g.add_node("finish", finish_node)
    g.add_edge(START, "plan")
    g.add_edge("plan", "execute")
    g.add_edge("execute", "analyze")
    g.add_conditional_edges("analyze", route_after_analyze,
                            {"continue": "execute", "finish": "finish"})
    g.add_edge("finish", END)
    return g.compile()


def _suspicious(state: dict) -> bool:
    if state.get("last_action_result") == "no_response":
        return True
    for v in (state.get("indicators") or {}).values():
        if isinstance(v, (int, float)) and v < 0:
            return True
        if str(v).lower() in ("nan", "undefined"):
            return True
    return False
