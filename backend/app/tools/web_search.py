"""联网搜索工具：DuckDuckGo 搜索（无需 API Key），多策略降级保证可用"""
import logging
import re
from typing import Optional

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


class WebSearchTool:
    """联网搜索：优先 ddgs 库，失败回退 DuckDuckGo HTML / Bing 抓取"""

    name = "web_search"
    description = "在互联网上搜索游戏 BUG、错误信息、已知问题等相关资料"

    def search(self, query: str, max_results: Optional[int] = None) -> list[dict]:
        """返回 [{title, url, snippet}]；任何策略失败都静默降级到下一策略"""
        limit = max_results or settings.WEB_SEARCH_MAX_RESULTS
        if not settings.WEB_SEARCH_ENABLED:
            return []
        for strategy in (self._via_ddgs, self._via_duck_html, self._via_bing):
            try:
                results = strategy(query, limit)
                if results:
                    logger.info("web_search[%s] '%s' -> %s 条", strategy.__name__, query, len(results))
                    return results
            except Exception as e:  # noqa: BLE001 - 搜索失败必须静默降级
                logger.warning("web_search 策略 %s 失败: %s", strategy.__name__, e)
        return []

    # ---- 策略 1: ddgs 库 ----
    def _via_ddgs(self, query: str, limit: int) -> list[dict]:
        try:
            from ddgs import DDGS  # 新包名
        except ImportError:
            from duckduckgo_search import DDGS  # 旧包名兼容
        out = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=limit):
                out.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", "") or r.get("url", ""),
                    "snippet": r.get("body", "") or r.get("snippet", ""),
                })
        return out

    # ---- 策略 2: DuckDuckGo HTML 版 ----
    def _via_duck_html(self, query: str, limit: int) -> list[dict]:
        resp = httpx.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={"User-Agent": _UA},
            timeout=15.0,
            follow_redirects=True,
        )
        resp.raise_for_status()
        return self._parse_links(resp.text, limit, host_filter="duckduckgo")

    # ---- 策略 3: Bing 网页版 ----
    def _via_bing(self, query: str, limit: int) -> list[dict]:
        resp = httpx.get(
            "https://www.bing.com/search",
            params={"q": query, "setlang": "zh-hans"},
            headers={"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9"},
            timeout=15.0,
            follow_redirects=True,
        )
        resp.raise_for_status()
        return self._parse_links(resp.text, limit, host_filter="bing")

    @staticmethod
    def _strip_tags(html: str) -> str:
        html = re.sub(r"<[^>]+>", "", html)
        return re.sub(r"\s+", " ", html).strip()

    def _parse_links(self, html: str, limit: int, host_filter: str) -> list[dict]:
        out: list[dict] = []
        # DuckDuckGo: <a class="result__a" href="...">title</a> + <a class="result__snippet">
        for m in re.finditer(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>(.*?)(?=<a[^>]+class="result__a"|</div>\s*</div>\s*</div>|$)',
            html, re.S):
            url, title, rest = m.group(1), self._strip_tags(m.group(2)), m.group(3)
            if "uddg=" in url:  # ddg 跳转链接解码
                mm = re.search(r"uddg=([^&]+)", url)
                if mm:
                    from urllib.parse import unquote
                    url = unquote(mm.group(1))
            sn = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', rest, re.S)
            snippet = self._strip_tags(sn.group(1)) if sn else ""
            if title and url:
                out.append({"title": title, "url": url, "snippet": snippet[:300]})
            if len(out) >= limit:
                break
        if out:
            return out
        # Bing: <li class="b_algo"> <h2 class=""><a href="...">title</a></h2> ... <p class="b_lineclamp...">snippet</p>
        for m in re.finditer(r'<li class="b_algo".*?<h2[^>]*><a[^>]+href="([^"]+)"[^>]*>(.*?)</a></h2>(.*?)</li>', html, re.S):
            url, title, rest = m.group(1), self._strip_tags(m.group(2)), m.group(3)
            sn = re.search(r"<p[^>]*>(.*?)</p>", rest, re.S)
            snippet = self._strip_tags(sn.group(1)) if sn else ""
            if title and url and not url.startswith("https://www.bing.com"):
                out.append({"title": title, "url": url, "snippet": snippet[:300]})
            if len(out) >= limit:
                break
        return out


web_search = WebSearchTool()
