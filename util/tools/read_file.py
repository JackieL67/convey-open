"""Read File Tool — 文件内容读取工具

支持格式：
  - PDF  (.pdf)  → PyMuPDF (fitz) 逐页提取文本，支持 page 参数
  - 文本类文件    → 直接 UTF-8 读取
  - 其他格式     → 返回"不支持的文件类型"提示

截断策略：内容超过 MAX_CHARS 字符时截断并提示。
错误策略：所有异常均捕获，以友好的中文错误信息返回，不向外抛异常。
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# 支持的文本扩展名
# ──────────────────────────────────────────────────────────────────────────────
TEXT_EXTENSIONS = {
    ".md", ".txt", ".py", ".js", ".ts",
    ".json", ".yaml", ".yml", ".csv",
    ".html", ".xml",
}


class ReadFileTool:
    """文件内容读取工具 — PDF (PyMuPDF) + 纯文本。

    Args:
        upload_dir: 用户上传文件的根目录路径，默认指向 convey 项目的 uploads 目录。
    """

    # 内容超过此字符数时截断
    MAX_CHARS = 8000

    def __init__(self, upload_dir: str = None):
        self.upload_dir = upload_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "user-portal", "data", "uploads")

    # ──────────────────────────────────────────────────────────────────────────
    # 公共 API
    # ──────────────────────────────────────────────────────────────────────────

    async def read(self, file_id: str, page: Optional[int] = None) -> dict:
        """异步读取文件内容（同步 I/O 在线程池中执行）。

        Args:
            file_id: 文件唯一标识符，对应 upload_dir 下的文件名（含扩展名）。
            page:    可选，PDF 页码（从 1 开始）。

        Returns:
            成功：{"content": "...", "file_type": "pdf"|"text", "filename": "...", "page": N}
            失败：{"content": "读取失败: ...", "error": "..."}
        """
        loop = asyncio.get_running_loop()
        # 将同步读取操作放到线程池，避免阻塞事件循环
        return await loop.run_in_executor(None, self._read_sync, file_id, page)

    # ──────────────────────────────────────────────────────────────────────────
    # 内部同步实现
    # ──────────────────────────────────────────────────────────────────────────

    def _read_sync(self, file_id: str, page: Optional[int]) -> dict:
        """同步读取文件内容，供线程池调用。"""

        # 1. 拼接完整路径，检查文件是否存在
        file_path = Path(self.upload_dir) / file_id
        if not file_path.exists():
            err = f"文件不存在: {file_id}"
            return {"content": f"读取失败: {err}", "error": err}
        if not file_path.is_file():
            err = f"路径不是文件: {file_id}"
            return {"content": f"读取失败: {err}", "error": err}

        ext = file_path.suffix.lower()  # 获取小写扩展名

        # 2. 按扩展名分派读取逻辑
        try:
            if ext == ".pdf":
                return self._read_pdf(file_path, page)
            elif ext in TEXT_EXTENSIONS:
                return self._read_text(file_path)
            else:
                # 不支持的文件类型
                msg = f"不支持的文件类型: {ext}"
                return {
                    "content": msg,
                    "file_type": "unsupported",
                    "filename": file_path.name,
                }
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            return {"content": f"读取失败: {err}", "error": err}

    def _read_pdf(self, file_path: Path, page: Optional[int]) -> dict:
        """使用 PyMuPDF (fitz) 读取 PDF 文件内容。

        Args:
            file_path: PDF 文件完整路径。
            page:      可选页码（从 1 开始）。None 表示读取全文。

        Returns:
            包含 content、file_type、filename、page、total_pages 的字典。
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            err = "PyMuPDF 未安装，请运行: pip install pymupdf"
            return {"content": f"读取失败: {err}", "error": err}

        with fitz.open(str(file_path)) as doc:
            total_pages = len(doc)

            if page is not None:
                # ── 读取指定页 ──────────────────────────────────────────────
                if page < 1 or page > total_pages:
                    err = f"页码超出范围: {page}，文件共 {total_pages} 页"
                    return {"content": f"读取失败: {err}", "error": err}
                # fitz 页码从 0 开始
                text = doc[page - 1].get_text()
                content = text.strip()
                # 单页截断
                if len(content) > self.MAX_CHARS:
                    content = content[: self.MAX_CHARS] + f"\n\n[内容已截断，当前页超过 {self.MAX_CHARS} 字符]"
                return {
                    "content": content,
                    "file_type": "pdf",
                    "filename": file_path.name,
                    "page": page,
                    "total_pages": total_pages,
                }
            else:
                # ── 读取全文 ─────────────────────────────────────────────────
                parts = []
                for i, pg in enumerate(doc, start=1):
                    parts.append(f"[第 {i} 页]\n{pg.get_text().strip()}")
                full_text = "\n\n".join(parts)

                truncated = False
                if len(full_text) > self.MAX_CHARS:
                    full_text = full_text[: self.MAX_CHARS]
                    truncated = True

                if truncated:
                    full_text += (
                        f"\n\n[内容已截断，文件共 {total_pages} 页，超过 {self.MAX_CHARS} 字符。"
                        "可使用 page 参数读取指定页，例如 page=1]"
                    )

                return {
                    "content": full_text,
                    "file_type": "pdf",
                    "filename": file_path.name,
                    "page": None,
                    "total_pages": total_pages,
                }

    def _read_text(self, file_path: Path) -> dict:
        """读取纯文本类文件（UTF-8，失败时降级 latin-1）。

        Args:
            file_path: 文件完整路径。

        Returns:
            包含 content、file_type、filename 的字典。
        """
        # 优先 UTF-8，失败则用 latin-1 兜底（防止编码错误）
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = file_path.read_text(encoding="latin-1")

        content = text
        truncated = False
        if len(content) > self.MAX_CHARS:
            content = content[: self.MAX_CHARS]
            truncated = True

        if truncated:
            content += f"\n\n[内容已截断，超过 {self.MAX_CHARS} 字符]"

        return {
            "content": content,
            "file_type": "text",
            "filename": file_path.name,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Registry Handler — 供 ToolRegistry.set_handler() 注入
# ──────────────────────────────────────────────────────────────────────────────

# 模块级工具实例（默认 upload_dir）
_tool = ReadFileTool()


async def handler(args: dict, context: dict) -> dict:
    """工具 handler，符合 ToolRegistry 接口规范。

    Args:
        args:    {"file_id": "xxx.pdf", "page": 1}  — page 可选
        context: {"email": "...", "session_id": "...", "upload_dir": "..."}

    Returns:
        {"content": "...", "file_type": "pdf", "filename": "...", ...}
    """
    file_id: str = args.get("file_id", "")
    page: Optional[int] = args.get("page")  # 可选，整数或 None

    if not file_id:
        return {
            "content": (
                "❌ read_file 失败：当前会话中没有可读取的文件。"
                "请等待用户上传文件后再使用此工具（如 PDF、Markdown、TXT 等）。"
                "不要重复调用 read_file，除非用户已经上传了新文件。"
            ),
            "error": "no_file_available",
        }

    # 如果 context 传入了自定义 upload_dir，则使用它；否则用模块默认实例
    upload_dir = context.get("upload_dir")
    tool = ReadFileTool(upload_dir=upload_dir) if upload_dir else _tool

    return await tool.read(file_id=file_id, page=page)
