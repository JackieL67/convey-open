"""Web Search Tool — Tavily 搜索引擎工具

通过 Tavily API 执行互联网搜索，返回格式化后的搜索结果。
支持作为独立工具直接调用，也可通过 ToolRegistry handler 接入执行器。
"""

from __future__ import annotations

import httpx


class WebSearchTool:
    """Tavily 搜索引擎工具

    使用 httpx.AsyncClient 向 Tavily REST API 发起异步 POST 请求，
    将原始结果格式化为 LLM 友好的 Markdown 文本。
    """

    # Tavily REST API 端点
    API_URL = "https://api.tavily.com/search"
    # 预置 API Key（可在初始化时覆盖）
    API_KEY = "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"

    def __init__(self, api_key: str | None = None) -> None:
        # 允许外部传入自定义 Key，未传则使用类常量
        self._api_key = api_key or self.API_KEY

    # ------------------------------------------------------------------
    # 核心搜索方法
    # ------------------------------------------------------------------

    async def search(self, query: str, max_results: int = 5) -> dict:
        """执行搜索，返回格式化结果字典。

        Args:
            query:       搜索关键词或自然语言问题
            max_results: 最多返回的结果条数，默认 5

        Returns:
            成功时：
                {
                    "content": "- [标题](url)\n  摘要\n...",   # LLM 友好文本
                    "results": [{"title": ..., "url": ..., "content": ...}, ...]
                }
            失败时：
                {
                    "content": "搜索失败: <原因>",
                    "error": "<异常信息>"
                }
        """
        # 构造请求体，search_depth=basic 速度快，满足大多数场景
        payload = {
            "api_key": self._api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        }

        try:
            # 使用 httpx 异步客户端，超时 10 秒防止长时间阻塞
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.API_URL, json=payload)
                # 非 2xx 状态码抛出 HTTPStatusError
                response.raise_for_status()
                data = response.json()

        except httpx.TimeoutException as exc:
            # 请求超时（连接超时 / 读取超时）
            msg = f"请求超时（10s）: {exc}"
            return {"content": f"搜索失败: {msg}", "error": msg}

        except httpx.HTTPStatusError as exc:
            # HTTP 错误响应（4xx / 5xx）
            msg = f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            return {"content": f"搜索失败: {msg}", "error": msg}

        except httpx.RequestError as exc:
            # 网络连接等底层错误
            msg = f"网络请求错误: {exc}"
            return {"content": f"搜索失败: {msg}", "error": msg}

        except Exception as exc:
            # 其他未预期错误（JSON 解析失败等）兜底
            msg = f"{type(exc).__name__}: {exc}"
            return {"content": f"搜索失败: {msg}", "error": msg}

        # ----------------------------------------------------------
        # 格式化搜索结果为 LLM 友好文本
        # ----------------------------------------------------------
        raw_results: list[dict] = data.get("results", [])

        if not raw_results:
            # API 正常响应但无结果（如查询过于生僻）
            return {
                "content": f"未找到与「{query}」相关的搜索结果。",
                "results": [],
            }

        lines: list[str] = [f"搜索「{query}」的结果：\n"]
        for idx, item in enumerate(raw_results, start=1):
            title   = item.get("title", "（无标题）").strip()
            url     = item.get("url", "").strip()
            snippet = (item.get("content") or item.get("snippet") or "").strip()

            # 每条结果：序号 + 标题链接 + 摘要缩进
            lines.append(f"{idx}. [{title}]({url})")
            if snippet:
                # 摘要截断，避免单条过长
                short_snippet = snippet[:300] + ("..." if len(snippet) > 300 else "")
                lines.append(f"   {short_snippet}")
            lines.append("")  # 空行分隔

        return {
            "content": "\n".join(lines).rstrip(),
            "results": raw_results,          # 保留原始列表，供 Portal 渲染链接卡片
        }


# ------------------------------------------------------------------
# Registry Handler 适配器 — 供 ToolExecutor / ToolRegistry 调用
# ------------------------------------------------------------------

# 模块级单例，避免每次调用都创建新实例
_tool_instance = WebSearchTool()


async def handler(args: dict, context: dict) -> dict:
    """ToolRegistry handler 入口。

    Args:
        args:    {"query": "...", "max_results": 5}
        context: {"email": "...", "session_id": "..."}  （当前未使用，保留扩展）

    Returns:
        {"content": "...", "results": [...]}  或  {"content": "搜索失败: ...", "error": "..."}
    """
    query       = args.get("query", "").strip()
    max_results = int(args.get("max_results", 5))

    # 查询词为空时快速返回错误，避免无意义的网络请求
    if not query:
        return {"content": "搜索失败: query 参数不能为空", "error": "query is empty"}

    return await _tool_instance.search(query=query, max_results=max_results)
