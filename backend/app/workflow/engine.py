"""轻量工作流引擎：LangGraph StateGraph 的等价简化实现

支持：节点注册、固定边、条件边、状态字典流转、START/END 语义。
不引入 langchain/langgraph 重依赖，语义与 LangGraph StateGraph 一致。
"""
from typing import Any, Callable

START = "__start__"
END = "__end__"


class StateGraph:
    """状态图：节点处理函数签名 fn(state: dict) -> dict（返回增量更新）"""

    def __init__(self) -> None:
        self._nodes: dict[str, Callable[[dict], dict]] = {}
        self._edges: dict[str, str] = {}
        self._conditional: dict[str, tuple[Callable[[dict], str], dict[str, str]]] = {}
        self._entry: str = ""

    def add_node(self, name: str, fn: Callable[[dict], dict]) -> "StateGraph":
        self._nodes[name] = fn
        return self

    def add_edge(self, a: str, b: str) -> "StateGraph":
        if a == START:
            self._entry = b
        else:
            self._edges[a] = b
        return self

    def add_conditional_edges(self, source: str, router: Callable[[dict], str],
                              mapping: dict[str, str]) -> "StateGraph":
        self._conditional[source] = (router, mapping)
        return self

    def compile(self) -> "CompiledGraph":
        if not self._entry:
            raise ValueError("工作流缺少入口边 (START -> node)")
        return CompiledGraph(self._nodes, self._edges, self._conditional, self._entry)


class CompiledGraph:
    def __init__(self, nodes, edges, conditional, entry) -> None:
        self.nodes = nodes
        self.edges = edges
        self.conditional = conditional
        self.entry = entry

    def invoke(self, state: dict | None = None) -> dict:
        """执行工作流：从 START 沿边流转直到 END。节点返回增量 merge 进 state。"""
        state = dict(state or {})
        current = self.entry
        guard = 0
        while current != END and current:
            guard += 1
            if guard > 200:
                raise RuntimeError("工作流疑似死循环（>200 跳）")
            fn = self.nodes.get(current)
            if fn is None:
                raise ValueError(f"工作流节点未注册: {current}")
            patch = fn(state) or {}
            state.update(patch)

            if current in self.conditional:
                router, mapping = self.conditional[current]
                key = router(state)
                current = mapping.get(key, END)
            else:
                current = self.edges.get(current, END)
        return state
