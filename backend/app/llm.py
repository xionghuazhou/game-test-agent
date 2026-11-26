"""LLM 客户端：OpenAI 兼容协议，对接 SenseNova 中转站（deepseek-v4-flash 思考模型）"""
import json
import re
import threading
import time
import logging
from typing import Any, Optional

import httpx

from .config import settings

logger = logging.getLogger(__name__)

# 中转站限流较严格：全局串行 + 最小调用间隔
_rate_lock = threading.Lock()
_last_call_ts = 0.0
_MIN_INTERVAL = 1.2  # 秒


class LLMError(RuntimeError):
    pass


class LLMClient:
    """轻量 OpenAI 兼容客户端（不依赖 openai 库，httpx 直连）"""

    def __init__(self) -> None:
        self.base_url = settings.LLM_BASE_URL.rstrip("/")
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL
        self.max_tokens = settings.LLM_MAX_TOKENS

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        timeout: float = 120.0,
    ) -> str:
        """对话补全。json_mode=True 时提示模型输出纯 JSON。返回最终 content 文本。"""
        if json_mode:
            messages = list(messages) + [
                {"role": "system", "content": "只输出一个合法的 JSON 对象，不要输出任何解释、markdown 代码块或其他文字。"}
            ]
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        last_err: Optional[str] = None
        global _last_call_ts
        for attempt in range(5):
            try:
                # 全局限流：串行 + 最小间隔，避免 429
                with _rate_lock:
                    wait = _MIN_INTERVAL - (time.time() - _last_call_ts)
                    if wait > 0:
                        time.sleep(wait)
                    resp = httpx.post(url, headers=headers, json=payload, timeout=timeout)
                    _last_call_ts = time.time()
                if resp.status_code == 429:
                    # 限流：指数退避后重试
                    backoff = min(2 ** attempt * 2, 20)
                    logger.warning("LLM 429 限流，%s 秒后重试(第%s次)", backoff, attempt + 1)
                    time.sleep(backoff)
                    last_err = "429 Too Many Requests"
                    continue
                resp.raise_for_status()
                data = resp.json()
                choice = data["choices"][0]["message"]
                content = (choice.get("content") or "").strip()
                reasoning = (choice.get("reasoning_content") or "").strip()
                if not content and reasoning:
                    # 思考模型偶发只回思考链：截取思考中的结论段兜底
                    content = reasoning
                return content
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
                last_err = str(e)
                logger.warning("LLM 调用失败(第%s次): %s", attempt + 1, last_err)
                time.sleep(min(2 ** attempt, 8))
        raise LLMError(f"LLM 调用失败: {last_err}")

    def chat_json(self, messages: list[dict], temperature: float = 0.2, timeout: float = 120.0) -> Any:
        """对话并解析 JSON 输出（自动剥离 markdown 代码块）"""
        raw = self.chat(messages, temperature=temperature, json_mode=True, timeout=timeout)
        return self.extract_json(raw)

    @staticmethod
    def extract_json(raw: str) -> Any:
        """从模型输出中尽力提取 JSON"""
        text = raw.strip()
        # 剥离 ```json ... ``` 包裹
        m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
        if m:
            text = m.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试截取第一个 { 到最后一个 }
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
            start, end = text.find("["), text.rfind("]")
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
        raise LLMError(f"模型输出不是合法 JSON: {raw[:300]}")


llm_client = LLMClient()
