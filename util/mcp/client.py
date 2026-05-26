"""MCP Client — Model Context Protocol 客户端 [预留]

连接已配置的 MCP 服务器，发现工具并调用。
LLM Bridge 在构建 tools 数组时可注入 MCP 工具。
"""

# TODO: Phase 2+ 实现
# 接口预想:
#   class MCPClient:
#       async def discover_tools(self) -> list[dict]:
#           """发现已配置 MCP 服务器的工具列表。"""
#
#       async def call_tool(self, name: str, args: dict) -> str:
#           """调用 MCP 工具，返回结果。"""
