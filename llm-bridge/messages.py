"""消息构建

将历史消息、当前用户消息、附件等组装为 OpenAI 格式的消息列表。
支持系统提示、附件 URL 注入、预留 tools/skills/MCP/context 接口。
"""

from dataclasses import dataclass


@dataclass
class Attachment:
    """附件信息"""
    file_id: str
    filename: str
    content_type: str
    url: str


def build_messages(
    history: list[dict],
    message: str,
    *,
    attachments: list[Attachment] | None = None,
    system_prompt: str | None = None,
    system_parts: dict | None = None,
    tools: list[dict] | None = None,
    skills: str | None = None,
    mcp_tools: list[dict] | None = None,
    context: str | None = None,
) -> list[dict]:
    """构建 OpenAI 格式的消息列表。

    Args:
        history:      Engine DB 中的历史消息 [{"role": ..., "content": ...}]
        message:      当前用户消息文本
        attachments:  附件列表（注入 URL 到 content）
        system_prompt: 系统提示（单个 system 消息，兼容旧代码）
        system_parts: 结构化系统部分（多个 system 消息，新流程）
                     {"system_prompt": str, "user_memory": str, "dynamic_context": str}
        tools:        工具定义 schemas [预留]
        skills:       技能渲染文本 [预留]
        mcp_tools:    MCP 工具定义 [预留]
        context:      压缩后的上下文文本 [预留]

    Returns:
        [{\"role\": \"system\", \"content\": ...}, ...历史..., {\"role\": \"user\", \"content\": ...}]
    """
    # TODO: Phase 1 实现
    messages: list[dict] = []

    # 1. 系统提示
    # 优先使用 system_parts（新流程），否则使用 system_prompt（兼容旧代码）
    if system_parts:
        # 多个 system 消息拆分
        # 消息 1：系统提示词（base_prompt + reply_rules）
        if system_parts.get("system_prompt"):
            messages.append({
                "role": "system",
                "content": system_parts["system_prompt"],
            })
        
        # 消息 2：用户记忆（如果有）
        if system_parts.get("user_memory"):
            messages.append({
                "role": "system",
                "content": f"## 用户记忆\n{system_parts['user_memory']}",
            })
        
        # 消息 3：动态上下文（时间 + 用户信息）
        if system_parts.get("dynamic_context"):
            messages.append({
                "role": "system",
                "content": system_parts["dynamic_context"],
            })
    else:
        # 兼容旧代码：单个 system 消息
        system = system_prompt or "你是一个有用的AI助手。"
        messages.append({"role": "system", "content": system})

    # 2. 历史消息
    messages.extend(history)

    # 3. 当前用户消息（注入附件 URL，空消息跳过）
    if message:
        final_content = message
        if attachments:
            attach_lines = []
            for att in attachments:
                # 兼容 Attachment 对象 和 dict 两种格式
                if isinstance(att, dict):
                    ct = att.get("content_type", "")
                    fname = att.get("filename", "")
                    url = att.get("url", "")
                else:
                    ct = att.content_type
                    fname = att.filename
                    url = att.url
                if ct.startswith("image/"):
                    attach_lines.append(f"[用户上传了图片: {fname}, URL: {url}]")
                else:
                    attach_lines.append(f"[用户上传了文件: {fname}, URL: {url}]")
            if attach_lines:
                final_content = "\\n".join(attach_lines) + ("\\n" + final_content if final_content else "")
        messages.append({"role": "user", "content": final_content})

    return messages
