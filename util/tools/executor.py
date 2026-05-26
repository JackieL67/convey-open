"""Tool Executor — 工具调用执行器

负责执行 LLM 产生的 tool_calls：
  - execute()     : 执行单个工具，计时，错误不上抛（返回 error 字段）
  - execute_all() : 并发执行多个工具调用（asyncio.gather），保持顺序

结果格式（单个）：
    {
        "id":          "call_xxx",          # 原始 tool_call id
        "name":        "web_search",        # 工具名
        "content":     "...",               # 工具返回的文本内容
        "elapsed_ms":  123,                 # 耗时（毫秒）
        "error":       "...",               # 仅在出错时出现
    }
"""

from __future__ import annotations

import asyncio
import time
import traceback
from typing import Any, Optional

# 使用包内的注册表单例
from .registry import ToolRegistry

# 模块级注册表单例，executor 与 registry 共享同一实例
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """返回模块级共享注册表实例（供外部注入 handler 使用）。"""
    return _registry


class ToolExecutor:
    """工具执行器：通过注册表查找 handler 并异步执行。

    Args:
        upload_dir: 用户上传文件根目录，传递给 handler 的 context
        registry:   工具注册表，默认使用模块级共享实例
    """

    def __init__(
        self,
        upload_dir: Optional[str] = None,
        registry: Optional[ToolRegistry] = None,
    ):
        # 上传文件目录，注入到每次调用的 context 中
        self.upload_dir = upload_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "user-portal", "data", "uploads")
        # 优先使用传入的注册表，否则使用模块共享实例
        self.registry = registry or _registry

    # ------------------------------------------------------------------
    # 核心执行方法
    # ------------------------------------------------------------------

    async def execute(
        self,
        name: str,
        args: dict,
        context: Optional[dict] = None,
    ) -> dict:
        """执行单个工具调用，返回包含结果和耗时的字典。

        不抛异常——所有运行时错误均捕获并放入返回值的 "error" 字段。

        Args:
            name:    工具名称
            args:    工具参数字典（来自 LLM 的 function arguments）
            context: 可选上下文（如 session_id、user_id 等）

        Returns:
            {
                "name":       工具名,
                "content":    工具返回内容（字符串或可序列化对象）,
                "elapsed_ms": 耗时毫秒数,
                "error":      错误信息（仅在出错时出现）,
            }
        """
        # 构建调用上下文，补充 upload_dir
        ctx = {"upload_dir": self.upload_dir, **(context or {})}

        start_ns = time.perf_counter_ns()
        result: dict[str, Any] = {"name": name}

        try:
            # 从注册表取 handler
            handler = self.registry.get_handler(name)
            if handler is None:
                raise ValueError(f"工具 '{name}' 的 handler 尚未注册或未注入")

            # 支持同步和异步 handler
            if asyncio.iscoroutinefunction(handler):
                content = await handler(args, ctx)
            else:
                # 同步函数放到线程池执行，避免阻塞事件循环
                loop = asyncio.get_running_loop()
                content = await loop.run_in_executor(None, handler, args, ctx)

            result["content"] = content

        except Exception as exc:
            # 捕获所有异常，返回错误信息而非上抛
            result["content"] = ""
            result["error"] = f"{type(exc).__name__}: {exc}"
            # 调试时可开启详细 traceback
            # result["traceback"] = traceback.format_exc()

        finally:
            # 计算耗时（纳秒转毫秒）
            elapsed_ns = time.perf_counter_ns() - start_ns
            result["elapsed_ms"] = elapsed_ns // 1_000_000

        return result

    async def execute_all(
        self,
        tool_calls: list[dict],
        context: Optional[dict] = None,
    ) -> list[dict]:
        """并发执行多个工具调用，保持输入顺序返回结果。

        Args:
            tool_calls: 工具调用列表，每项格式：
                        {
                            "id":   "call_xxx",   # LLM 生成的唯一 ID
                            "name": "web_search", # 工具名
                            "args": {...}          # 工具参数
                        }
            context:    可选上下文，传递给每个 execute()

        Returns:
            结果列表，与 tool_calls 顺序一一对应，每项格式：
            {
                "id":          "call_xxx",
                "name":        "web_search",
                "content":     "...",
                "elapsed_ms":  123,
                "error":       "...",   # 仅出错时存在
            }
        """
        if not tool_calls:
            return []

        # 为每个 tool_call 创建协程，asyncio.gather 并发执行
        async def _run_one(tc: dict) -> dict:
            call_id = tc.get("id", "")
            name = tc.get("name", "")
            args = tc.get("args", {})

            res = await self.execute(name=name, args=args, context=context)
            # 补充原始 call id，便于 LLM Bridge 做消息回填
            res["id"] = call_id
            return res

        # 并发执行，return_exceptions=False 让单个任务的异常仍被 _run_one 内部吞掉
        results = await asyncio.gather(*[_run_one(tc) for tc in tool_calls])
        return list(results)
