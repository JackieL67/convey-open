"""Convey User Portal · FastAPI Web Server

V2 架构:
  - Portal 是唯一对外 Web 服务 (FastAPI :3000)
  - Engine 是内部微服务（通过 Python RPC 被 Portal 调用）
  - Portal 和 Engine 中心化部署在一起
  - 前端 fetch('/api/...') 不变，后端 handler 内部调 Engine RPC

当前阶段: Engine 已实现（ConversationEngine），Portal 默认通过 RPC 调用。
JSON 文件回退仅在 CONVEY_ENGINE_BACKEND=json 时可用（开发模式）。

认证: HMAC-SHA256 token（见 auth.py）。
"""

from pathlib import Path
import sys
import logging
import uuid
import time
import hashlib
import json

_convey_root = str(Path(__file__).parent.parent)
if _convey_root not in sys.path:
    sys.path.insert(0, _convey_root)

# 公网访问 URL（用于文件链接等需要绝对路径的场景）
import os


def _resolve_public_url() -> str:
    env_url = os.getenv("CONVEY_PUBLIC_URL")
    if env_url:
        return env_url
    # Fallback to localhost — set CONVEY_PUBLIC_URL for production
    port = os.getenv("CONVEY_PORT", "3000")
    return f"http://localhost:{port}"


PUBLIC_URL = _resolve_public_url()

from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from engine_client import create_engine_client
from auth import generate_token, validate_token
from crm import crm

logger = logging.getLogger("convey.portal")

# ── Pydantic 请求模型 ──


class ChatOptions(BaseModel):
    reasoning_level: str = "medium"  # low / medium / high / max
    reply_style: str = "normal"      # normal / concise / detailed
    model: str = ""                  # 留空=默认模型


class AttachmentInfo(BaseModel):
    file_id: str
    filename: str
    content_type: str = ""


class ChatRequest(BaseModel):
    message: str
    email: str
    session_id: str = ""
    settings: ChatOptions = ChatOptions()
    attachments: list[AttachmentInfo] = []


class EmailRequest(BaseModel):
    email: str
    device_id: str
    invite_code: str = ""


class NewSessionRequest(BaseModel):
    email: str


class SwitchSessionRequest(BaseModel):
    email: str


class SystemPromptRequest(BaseModel):
    system_prompt: str


class ReplyRulesRequest(BaseModel):
    reply_rules: str


class ContextPreviewRequest(BaseModel):
    email: str
    session_id: str
    message: str


# ── Engine Client 初始化 ──

DATA_DIR = Path(__file__).parent / "data"
engine = create_engine_client(DATA_DIR)


# ── FastAPI 应用 ──

app = FastAPI(title="Convey", version="0.3.0")

# CORS（允许移动端 WebView 访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 全局异常处理 ──


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """捕获未处理异常，返回用户友好错误 + error_id。"""
    error_id = uuid.uuid4().hex[:8]
    logger.error("[%s] Unhandled exception at %s: %s", error_id, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "请求失败，请稍后再试", "error_id": error_id},
    )


# ── Token 认证依赖 ──


async def require_auth(request: Request) -> str:
    """
    验证 Authorization Bearer token，返回 email。

    所有 /api/* 端点（/api/auth 除外）通过此依赖获取认证用户。
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "缺少认证凭证，请重新登录")

    token = auth_header[7:].strip()
    email = validate_token(token)
    if not email:
        raise HTTPException(401, "认证凭证无效或已过期，请重新登录")

    return email


# ── 认证端点（无需 token）──


@app.post("/api/auth")
async def auth(req: EmailRequest):
    """邮箱认证（首次或新设备）。返回用户信息 + token。"""
    if not req.email or "@" not in req.email:
        raise HTTPException(400, "请输入有效的邮箱地址")

    # CRM 邀请码检查：未注册邮箱需要邀请码
    if not crm.is_registered(req.email):
        if not req.invite_code:
            return JSONResponse(
                status_code=403,
                content={"need_invite": True, "remaining": crm.get_remaining_count()},
            )
        ok, msg = crm.validate_and_register(req.email, req.invite_code)
        if not ok:
            return JSONResponse(
                status_code=403,
                content={"need_invite": True, "error": msg, "remaining": crm.get_remaining_count()},
            )

    try:
        result = engine.auth(req.email, req.device_id)
        token = generate_token(req.email)
        result["token"] = token
        return result
    except Exception:
        raise HTTPException(500, "认证失败")


# ── 用户端点（需认证）──


@app.get("/api/user/{email}")
async def get_user(email: str, auth_email: str = Depends(require_auth)):
    """查询用户信息。token email 必须匹配路径 email。"""
    if email != auth_email:
        raise HTTPException(403, "无权访问该用户信息")
    try:
        return engine.get_user(email)
    except KeyError:
        raise HTTPException(404, "用户不存在")
    except Exception as e:
        raise HTTPException(500, "查询失败")


# ── Session 管理端点（需认证）──


@app.post("/api/sessions/new")
async def new_session(req: NewSessionRequest, auth_email: str = Depends(require_auth)):
    """创建新会话。"""
    if req.email != auth_email:
        raise HTTPException(403, "无权操作该用户")
    try:
        session_id = engine.create_session(req.email)
        return {"session_id": session_id, "message": "新对话已创建"}
    except KeyError:
        raise HTTPException(404, "用户不存在")
    except Exception as e:
        raise HTTPException(500, "创建会话失败")


@app.post("/api/sessions/switch")
async def switch_session(req: SwitchSessionRequest, session_id: str = "", auth_email: str = Depends(require_auth)):
    """切换到指定会话。"""
    if req.email != auth_email:
        raise HTTPException(403, "无权操作该用户")
    try:
        ok = engine.switch_session(req.email, session_id)
        if not ok:
            raise HTTPException(400, "会话不存在")
        return {"session_id": session_id, "message": "已切换到会话"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, "切换会话失败")


@app.get("/api/sessions/{email}")
async def list_sessions(email: str, auth_email: str = Depends(require_auth)):
    """获取用户的所有会话列表。"""
    if email != auth_email:
        raise HTTPException(403, "无权访问该用户会话")
    try:
        sessions = engine.list_sessions(email)
        return {"sessions": sessions}
    except KeyError:
        raise HTTPException(404, "用户不存在")
    except Exception as e:
        raise HTTPException(500, "获取会话列表失败")


@app.delete("/api/sessions/{email}/{session_id}")
async def delete_session(email: str, session_id: str, auth_email: str = Depends(require_auth)):
    """删除指定会话。"""
    if email != auth_email:
        raise HTTPException(403, "无权操作该用户会话")
    try:
        result = engine.delete_session(email, session_id)
        if not result.get("ok"):
            raise HTTPException(404, "会话不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, "删除失败")


@app.get("/api/conversations/{email}/{session_id}")
async def get_conversation(email: str, session_id: str, auth_email: str = Depends(require_auth)):
    """获取指定会话的对话历史。"""
    if email != auth_email:
        raise HTTPException(403, "无权访问该用户对话")
    try:
        messages = engine.get_history(email, session_id)
        return {"messages": messages}
    except PermissionError:
        raise HTTPException(404, "会话不存在")
    except Exception as e:
        raise HTTPException(500, "获取对话历史失败")


# ── 用户设置端点（需认证）──


@app.get("/api/settings/{email}/system-prompt")
async def get_system_prompt_endpoint(email: str, auth_email: str = Depends(require_auth)):
    """获取用户的系统提示词"""
    if email != auth_email:
        raise HTTPException(403, "无权访问")
    try:
        prompt = crm.get_system_prompt(email)
        return {"email": email, "system_prompt": prompt}
    except Exception as e:
        raise HTTPException(500, "获取系统提示词失败")


@app.put("/api/settings/{email}/system-prompt")
async def set_system_prompt_endpoint(email: str, req: SystemPromptRequest, auth_email: str = Depends(require_auth)):
    """更新用户的系统提示词"""
    if email != auth_email:
        raise HTTPException(403, "无权操作")
    try:
        crm.set_system_prompt(email, req.system_prompt)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, "更新系统提示词失败")


@app.get("/api/settings/{email}/reply-rules")
async def get_reply_rules_endpoint(email: str, auth_email: str = Depends(require_auth)):
    """获取用户的回复规范"""
    if email != auth_email:
        raise HTTPException(403, "无权访问")
    try:
        rules = crm.get_reply_rules(email)
        return {"email": email, "reply_rules": rules}
    except Exception as e:
        raise HTTPException(500, "获取回复规范失败")


@app.put("/api/settings/{email}/reply-rules")
async def set_reply_rules_endpoint(email: str, req: ReplyRulesRequest, auth_email: str = Depends(require_auth)):
    """更新用户的回复规范"""
    if email != auth_email:
        raise HTTPException(403, "无权操作")
    try:
        crm.set_reply_rules(email, req.reply_rules)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, "更新回复规范失败")



@app.post("/api/settings/{email}/reply-rules/reset")
async def reset_reply_rules_endpoint(email: str, auth_email: str = Depends(require_auth)):
    """恢复回复规范为默认值"""
    if email != auth_email:
        raise HTTPException(403, "无权操作")
    try:
        default = "## 回复规范\n- 用 Markdown 格式回复\n- 代码块标注使用的编程语言\n- 不确定时直接说明，不要编造\n- 用中文回复"
        crm.set_reply_rules(email, default)
        return {"ok": True, "reply_rules": default}
    except Exception as e:
        raise HTTPException(500, "重置回复规范失败")


# ── Prompt 上下文预览（需认证）──


@app.post("/api/context-preview")
async def context_preview(req: ContextPreviewRequest, auth_email: str = Depends(require_auth)):
    """返回当前会话即将发给 LLM 的完整上下文预览"""
    if req.email != auth_email:
        raise HTTPException(403, "无权访问")
    try:
        # 先尝试读快照
        snapshot = crm.get_context_snapshot(req.email)
        if snapshot:
            # 快照兼容性处理：旧快照格式只有 system_prompt，需要转换为新格式
            if "system_prompt" in snapshot and "user_memory" not in snapshot:
                # 旧格式：整个 system_prompt 放在 system_prompt 区
                old_system_prompt = snapshot.get("system_prompt", "")
                snapshot["system_prompt"] = old_system_prompt
                snapshot["user_memory"] = ""
                snapshot["dynamic_context"] = ""
                snapshot["system_token_estimate"] = max(1, len(old_system_prompt) // 4)
                snapshot["user_memory_token_estimate"] = 0
                snapshot["dynamic_context_token_estimate"] = 0
            # 补全新字段（附件/工具状态）—— 快照可能缺这些
            if "attachments_count" not in snapshot:
                snapshot["attachments_count"] = 0
                snapshot["attachments"] = []
            if "tools_count" not in snapshot:
                from util.tools import get_registry
                tools = get_registry().get_definitions()
                snapshot["active_tools"] = [t["function"]["name"] for t in tools]
                snapshot["tools_count"] = len(tools)
            return snapshot
        # 无快照时回退到实时生成
        result = await engine.get_context_preview(req.email, req.session_id, req.message)
        return result
    except PermissionError:
        raise HTTPException(404, "会话不存在")
    except Exception as e:
        logger.error("Failed to get context preview: %s", e)
        raise HTTPException(500, "获取上下文预览失败")


# ── 文件上传（需认证）──

UPLOAD_DIR = Path(__file__).parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    auth_email: str = Depends(require_auth),
):
    """
    上传文件。返回 file_id 和访问 URL。

    支持图片、PDF、文本等。最大 10MB。
    """
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"文件太大（最大 {MAX_FILE_SIZE // 1024 // 1024}MB）")

    # 生成 file_id: 基于内容哈希 + 时间戳
    content_hash = hashlib.md5(content).hexdigest()[:8]
    ts = int(time.time())
    ext = Path(file.filename).suffix if file.filename else ""
    file_id = f"{ts}_{content_hash}{ext}"

    # 保存文件
    file_path = UPLOAD_DIR / file_id
    file_path.write_bytes(content)

    url = f"{PUBLIC_URL}/api/files/{file_id}"
    return {
        "file_id": file_id,
        "filename": file.filename,
        "content_type": file.content_type or "application/octet-stream",
        "size": len(content),
        "url": url,
    }


@app.get("/api/files/{file_id}")
async def get_file(file_id: str, request: Request):
    """
    访问已上传的文件。

    支持两种认证方式：
    1. Authorization Bearer token（API 调用）
    2. 无认证（<img src> / <a href> 等浏览器直接访问需要公开访问文件）

    注意：此端点故意不强制要求认证，因为前端 <img> 标签和 <a> 标签
    无法携带自定义 Authorization header。文件 ID 本身含有内容哈希，
    具有一定的不可猜测性，足以防止随机枚举。
    """
    file_path = UPLOAD_DIR / file_id
    if not file_path.exists():
        raise HTTPException(404, "文件不存在")
    return FileResponse(file_path)


# ── 命令处理 ──

COMMAND_HELP = {
    "/reset": "重置当前会话，开始新对话",
    "/status": "查看系统状态",
    "/help": "显示可用命令列表",
}


def _handle_command(cmd: str, email: str, session_id: str) -> StreamingResponse:
    """处理 / 命令，返回 SSE 流式响应。"""
    parts = cmd.split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    async def generate():
        if command == "/reset":
            # 创建新会话
            new_sid = engine.create_session(email)
            result = f"✅ 会话已重置。新会话: {new_sid[:16]}..."
            sse_data = json.dumps({"choices": [{"delta": {"content": result}}]}, ensure_ascii=False)
            yield f"data: {sse_data}\n\n"
            yield f"event: done\ndata: {json.dumps({'type':'done','response':result}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        elif command == "/status":
            health_data = {
                "backend": "rpc",
                "version": "0.3.0",
                "invite_codes_remaining": crm.get_remaining_count(),
            }
            result = "📊 系统状态\n" + json.dumps(health_data, indent=2, ensure_ascii=False)
            sse_data = json.dumps({"choices": [{"delta": {"content": result}}]}, ensure_ascii=False)
            yield f"data: {sse_data}\n\n"
            yield f"event: done\ndata: {json.dumps({'type':'done','response':result}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        elif command == "/help":
            lines = ["📋 可用命令:"]
            for c, desc in COMMAND_HELP.items():
                lines.append(f"  {c} — {desc}")
            result = "\n".join(lines)
            sse_data = json.dumps({"choices": [{"delta": {"content": result}}]}, ensure_ascii=False)
            yield f"data: {sse_data}\n\n"
            yield f"event: done\ndata: {json.dumps({'type':'done','response':result}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        else:
            result = f"❓ 未知命令: {command}\n输入 /help 查看可用命令"
            sse_data = json.dumps({"choices": [{"delta": {"content": result}}]}, ensure_ascii=False)
            yield f"data: {sse_data}\n\n"
            yield f"event: done\ndata: {json.dumps({'type':'done','response':result}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ── 对话端点（需认证）──


@app.post("/api/chat")
async def chat(req: ChatRequest, auth_email: str = Depends(require_auth)):
    """发送消息并获取回复（SSE 流式）。支持 / 命令。"""
    if req.email != auth_email:
        raise HTTPException(403, "无权操作该用户")

    # ── 命令处理 ──
    msg = req.message.strip()
    if msg.startswith("/"):
        return _handle_command(msg, req.email, req.session_id)

    # 确定 session_id
    session_id = req.session_id
    if not session_id:
        try:
            user_info = engine.get_user(req.email)
            if user_info:
                session_id = user_info["session_id"]
        except Exception:
            pass
    if not session_id:
        import uuid
        session_id = f"conv_{uuid.uuid4().hex[:12]}"

    # 流式回复（传递 settings + attachments）
    options = {
        "reasoning_level": req.settings.reasoning_level,
        "reply_style": req.settings.reply_style,
        "model": req.settings.model,
    }

    # 构建附件列表
    attach_list = None
    if req.attachments:
        attach_list = [
            {"file_id": a.file_id, "filename": a.filename,
             "content_type": a.content_type, "url": f"{PUBLIC_URL}/api/files/{a.file_id}"}
            for a in req.attachments
        ]

    async def generate():
        async for chunk in engine.chat_stream(req.email, session_id, req.message, options=options, attachments=attach_list):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── 健康检查（无需认证）──


@app.get("/api/health")
async def health():
    """
    健康检查端点。

    返回 Portal/Engine/DB 状态，不暴露 secret 或内部路径。
    """
    import os
    result = {
        "status": "ok",
        "backend": os.environ.get("CONVEY_ENGINE_BACKEND", "rpc"),
        "version": "0.3.0",
    }

    # 检查 Engine DB 可达性
    try:
        engine.get_user("__health_check__")
        result["engine_db"] = "ok"
    except Exception:
        result["engine_db"] = "error"
        result["status"] = "degraded"

    # 检查 CRM DB
    try:
        crm.get_remaining_count()
        result["crm"] = "ok"
        result["invite_codes_remaining"] = crm.get_remaining_count()
    except Exception:
        result["crm"] = "error"

    return result


@app.get("/api/recovery/{email}")
async def get_recovery(email: str, session_id: str = "", auth_email: str = Depends(require_auth)):
    """
    获取待恢复的消息（pending 状态的用户消息）。

    前端加载会话时调用，检查是否有中断的消息需要重试。
    """
    if email != auth_email:
        raise HTTPException(403, "无权访问")
    try:
        pending = engine.get_pending_messages(session_id=session_id if session_id else None)
        return {"pending_messages": pending}
    except Exception as e:
        raise HTTPException(500, "查询恢复消息失败")


# ── 静态文件（无需认证）──

# React build output (priority) or legacy HTML prototype
STATIC_DIR = Path(__file__).parent / "static"
PROTOTYPE_DIR = Path(__file__).parent.parent / "prototype"
REACT_BUILD = STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists()

if REACT_BUILD:
    # Serve React build assets
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="react-assets")
elif PROTOTYPE_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(PROTOTYPE_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """首页 — 返回 Convey UI (React build or legacy HTML)."""
    if REACT_BUILD:
        return HTMLResponse((STATIC_DIR / "index.html").read_text())
    html_path = PROTOTYPE_DIR / "convey-app.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    return HTMLResponse("<h1>Convey</h1><p>UI 文件未找到。</p>")


if __name__ == "__main__":
    port = int(os.getenv("CONVEY_PORT", "3000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
