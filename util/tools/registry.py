"""Tool Registry — 工具注册表

管理所有可用工具的 schema 定义及对应处理函数。
LLM Bridge 构建消息时从注册表获取 tools 数组（OpenAI function calling 格式）。
Handler 可延迟注入，启动时由 chat_handler 负责绑定真实实现。
"""

from __future__ import annotations
from typing import Callable, Optional


class ToolRegistry:
    """工具注册表：统一管理 schema 定义和处理函数的映射关系。

    内部存储格式：
        _tools = {
            "<工具名>": {
                "schema": {<OpenAI function 对象>},
                "handler": <callable 或 None>
            }
        }
    """

    def __init__(self):
        # 工具字典：name → {schema, handler}
        self._tools: dict[str, dict] = {}
        # 初始化时注册 3 个内置工具（handler 先置 None，由外部延迟注入）
        self._register_builtin_tools()

    # ------------------------------------------------------------------
    # 内置工具注册
    # ------------------------------------------------------------------

    def _register_builtin_tools(self) -> None:
        """注册 3 个内置工具的 schema 定义，handler 先设为 None。"""

        # 1. web_search — 网络搜索
        self.register(
            name="web_search",
            schema={
                "name": "web_search",
                "description": (
                    "搜索互联网获取最新信息。"
                    "当需要实时信息、新闻、或知识库中没有的内容时使用。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词或问题",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "最多返回的结果数量（默认 5）",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            },
            handler=None,
        )

        # 2. read_file — 读取上传文件
        self.register(
            name="read_file",
            schema={
                "name": "read_file",
                "description": (
                    "读取用户上传文件的内容。"
                    "支持 PDF、Markdown、TXT、代码文件等。"
                    "当用户询问文件内容时使用。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_id": {
                            "type": "string",
                            "description": "文件唯一标识符，从附件列表获取",
                        },
                        "page": {
                            "type": "integer",
                            "description": "可选，PDF 文件的页码（从 1 开始）",
                        },
                    },
                    "required": ["file_id"],
                },
            },
            handler=None,
        )

        # 3. describe_image — 图片识别/描述
        self.register(
            name="describe_image",
            schema={
                "name": "describe_image",
                "description": (
                    "识别/描述用户上传的图片内容。"
                    "当用户询问图片中有什么时使用。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_id": {
                            "type": "string",
                            "description": "图片文件唯一标识符，从附件列表获取",
                        },
                        "question": {
                            "type": "string",
                            "description": "可选，针对图片的具体问题（如：图中有几个人）",
                        },
                    },
                    "required": ["file_id"],
                },
            },
            handler=None,
        )

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        schema: dict,
        handler: Optional[Callable] = None,
    ) -> None:
        """注册工具 schema 及处理函数。

        Args:
            name:    工具名称，唯一标识
            schema:  OpenAI function 对象（不含外层 type/function 包装）
            handler: 处理函数，可为 None（稍后通过 set_handler 注入）
        """
        self._tools[name] = {
            "schema": schema,
            "handler": handler,
        }

    def get_definitions(self) -> list[dict]:
        """返回所有已注册工具的 OpenAI function calling 格式定义列表。

        格式：[{"type": "function", "function": {...}}, ...]
        """
        return [
            {"type": "function", "function": entry["schema"]}
            for entry in self._tools.values()
        ]

    def get_handler(self, name: str) -> Optional[Callable]:
        """按工具名获取处理函数。

        Returns:
            对应的 handler callable，若工具不存在则返回 None
        """
        entry = self._tools.get(name)
        if entry is None:
            return None
        return entry["handler"]

    def set_handler(self, name: str, handler: Callable) -> None:
        """设置/更新已注册工具的处理函数（用于延迟绑定）。

        Args:
            name:    已注册的工具名
            handler: 实际处理函数

        Raises:
            KeyError: 工具名不存在时抛出
        """
        if name not in self._tools:
            raise KeyError(f"工具 '{name}' 尚未注册，请先调用 register()")
        self._tools[name]["handler"] = handler

    def list_names(self) -> list[str]:
        """返回所有已注册工具的名称列表（调试用）。"""
        return list(self._tools.keys())
