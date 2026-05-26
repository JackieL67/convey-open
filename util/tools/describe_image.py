"""Describe Image Tool — 跨模型视觉识别

使用 Claude Sonnet via zenmux 对用户上传的图片进行识别和描述。
支持 base64 编码、结果缓存、可选定向提问，以及完整的错误兜底。
"""

from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Optional

import httpx


# MIME type 到 Claude API 接受的 media_type 的映射表
# Claude 只接受这 4 种图片格式
_MIME_MAP: dict[str, str] = {
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".gif":  "image/gif",
    ".webp": "image/webp",
}

# 支持的图片扩展名集合（用于快速校验）
_SUPPORTED_EXTS = frozenset(_MIME_MAP.keys())


class DescribeImageTool:
    """跨模型视觉识别 — Claude Sonnet via zenmux

    通过 zenmux 代理调用 Anthropic Claude Sonnet 的视觉能力，
    将图片 base64 编码后发送，获取中文描述。

    Attributes:
        ZENMUX_URL: zenmux Anthropic 兼容 API 地址
        upload_dir: 用户上传文件根目录
        _cache:     file_id → 描述结果的内存缓存
    """

    ZENMUX_URL = "https://zenmux.ai/api/anthropic/v1/messages"
    # 使用的模型名称（Claude Sonnet 最新稳定版）
    MODEL = "claude-sonnet-4-20250514"
    # 单次调用最大生成 token 数
    MAX_TOKENS = 1024
    # HTTP 请求超时秒数
    TIMEOUT = 30.0

    def __init__(self, upload_dir: str = None):
        # 上传目录，默认为 convey 标准路径
        self.upload_dir = upload_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "user-portal", "data", "uploads")
        # file_id → 描述结果的内存缓存（图片不可变，同 file_id 不重复调 API）
        self._cache: dict[str, str] = {}

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    async def describe(self, file_id: str, question: str = None) -> dict:
        """识别图片内容，返回中文描述。

        Args:
            file_id:  图片文件名（如 "1779780323_ea52b151.png"），
                      在 upload_dir 下查找。
            question: 可选的定向问题，如 "图中有几个人？"。
                      不传则使用默认通用描述提示。

        Returns:
            成功: {"content": "图片描述...", "model": "claude-sonnet-4-20250514", "cached": bool}
            失败: {"content": "识别失败: ...", "error": "..."}
        """
        # 1. 检查缓存（同一 file_id 直接返回已缓存结果）
        cache_key = f"{file_id}::{question or ''}"
        if cache_key in self._cache:
            return {
                "content": self._cache[cache_key],
                "model": self.MODEL,
                "cached": True,
            }

        # 2. 构建图片文件路径并校验
        file_path = Path(self.upload_dir) / file_id
        if not file_path.exists():
            err = f"文件不存在: {file_id}"
            return {"content": f"识别失败: {err}", "error": err}

        # 3. 校验文件类型（只处理图片）
        ext = file_path.suffix.lower()
        if ext not in _SUPPORTED_EXTS:
            err = f"不支持的文件类型: {ext}，仅支持 {', '.join(sorted(_SUPPORTED_EXTS))}"
            return {"content": f"识别失败: {err}", "error": err}

        media_type = _MIME_MAP[ext]

        # 4. 读取文件并 base64 编码（标准 base64，不含换行符）
        try:
            raw_bytes = file_path.read_bytes()
            # base64.b64encode 默认输出不含换行符的标准 base64
            b64_data = base64.b64encode(raw_bytes).decode("ascii")
        except OSError as exc:
            err = f"读取文件失败: {exc}"
            return {"content": f"识别失败: {err}", "error": err}

        # 5. 构建提示词（支持定向提问）
        prompt_text = question if question else "请详细描述这张图片的内容，包括主体、颜色、构图、文字等所有可见信息，使用中文回答。"

        # 6. 构建 Anthropic Messages API 请求体
        request_body = {
            "model": self.MODEL,
            "max_tokens": self.MAX_TOKENS,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            # 图片 content block：base64 格式
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64_data,
                            },
                        },
                        {
                            # 文本 content block：提问内容
                            "type": "text",
                            "text": prompt_text,
                        },
                    ],
                }
            ],
        }

        # 7. 获取 API Key（从环境变量读取）
        api_key = os.environ.get("ZENMUX_API_KEY", "")
        if not api_key:
            err = "ZENMUX_API_KEY 环境变量未设置"
            return {"content": f"识别失败: {err}", "error": err}

        # 8. 调用 zenmux Claude API
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                response = await client.post(
                    self.ZENMUX_URL,
                    json=request_body,
                    headers=headers,
                )
        except httpx.TimeoutException:
            err = f"请求超时（>{self.TIMEOUT}s）"
            return {"content": f"识别失败: {err}", "error": err}
        except httpx.RequestError as exc:
            err = f"网络请求错误: {exc}"
            return {"content": f"识别失败: {err}", "error": err}

        # 9. 解析响应
        if response.status_code != 200:
            # 提取 API 返回的错误消息
            try:
                err_body = response.json()
                api_err = (
                    err_body.get("error", {}).get("message")
                    or err_body.get("error")
                    or response.text[:200]
                )
            except Exception:
                api_err = response.text[:200]
            err = f"API 错误 {response.status_code}: {api_err}"
            return {"content": f"识别失败: {err}", "error": err}

        try:
            resp_json = response.json()
            # Anthropic API 响应格式: {"content": [{"type": "text", "text": "..."}]}
            content_blocks = resp_json.get("content", [])
            description = ""
            for block in content_blocks:
                if block.get("type") == "text":
                    description += block.get("text", "")
        except Exception as exc:
            err = f"解析响应失败: {exc}"
            return {"content": f"识别失败: {err}", "error": err}

        if not description:
            err = "API 返回空内容"
            return {"content": f"识别失败: {err}", "error": err}

        # 10. 写入缓存并返回
        self._cache[cache_key] = description
        return {
            "content": description,
            "model": self.MODEL,
            "cached": False,
        }

    def clear_cache(self, file_id: str = None) -> None:
        """清除缓存。

        Args:
            file_id: 指定 file_id 清除对应条目；不传则清除全部缓存。
        """
        if file_id is None:
            self._cache.clear()
        else:
            # 删除所有以该 file_id 开头的缓存 key（含不同 question 的变体）
            keys_to_del = [k for k in self._cache if k.startswith(f"{file_id}::")]
            for k in keys_to_del:
                del self._cache[k]


# ------------------------------------------------------------------
# Registry Handler — 供 ToolRegistry.set_handler() 注入
# ------------------------------------------------------------------

# 模块级单例，避免重复实例化（缓存跨调用共享）
_tool_instance: Optional[DescribeImageTool] = None


def _get_tool(upload_dir: str = None) -> DescribeImageTool:
    """获取或创建 DescribeImageTool 单例。"""
    global _tool_instance
    if _tool_instance is None:
        _tool_instance = DescribeImageTool(upload_dir=upload_dir)
    return _tool_instance


async def handler(args: dict, context: dict) -> dict:
    """ToolRegistry handler 入口。

    Args:
        args:    工具调用参数，格式：
                 {"file_id": "xxx.png", "question": "图片里有几个人？"}
        context: 执行上下文，包含 {"upload_dir": "..."} 等信息

    Returns:
        {"content": "图片描述...", "model": "...", "cached": bool}
        或错误格式 {"content": "识别失败: ...", "error": "..."}
    """
    # 从 context 中获取 upload_dir（由 ToolExecutor 注入）
    upload_dir = context.get("upload_dir")

    # 获取工具单例（首次调用时根据 upload_dir 初始化）
    tool = _get_tool(upload_dir)

    # 提取参数
    file_id = args.get("file_id", "").strip()
    question = args.get("question", None)

    if not file_id:
        return {
            "content": "识别失败: 缺少 file_id 参数",
            "error": "缺少必填参数: file_id",
        }

    # 调用核心识别方法
    return await tool.describe(file_id=file_id, question=question)
