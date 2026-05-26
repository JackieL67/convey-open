"""Context — 上下文裁剪/摘要 [预留]

当消息列表超过 token 限制时，裁剪或摘要历史。
LLM Bridge 在主循环开始前调用。
"""


class ContextManager:
    """管理对话上下文，包括构建系统提示词和压缩历史记录。"""

    def build_system_parts(
        self,
        base_prompt: str,        # 基础系统提示，来自 EngineConfig.system_prompt
        user_info: dict,         # {"email": str}，后续可能扩展 name 等
        memories: str,           # 跨会话记忆文本（空串表示无记忆）
        timestamp: str,          # ISO 格式时间戳
        reply_rules: str = "",   # 回复规范
        attachments: list = None, # 当前会话附件列表 [{"filename": ..., "file_id": ...}]
    ) -> dict:
        """构建结构化系统提示词部分。

        拆分为三个独立部分：系统提示词、用户记忆、动态上下文。

        Args:
            base_prompt: 基础系统提示
            user_info: 用户信息字典，包含 email 等字段
            memories: 跨会话记忆文本，空串表示无记忆
            timestamp: ISO 格式时间戳
            reply_rules: 回复规范文本，空串表示无规范
            attachments: 当前会话附件列表

        Returns:
            {
                "system_prompt": str,      # base_prompt + reply_rules
                "user_memory": str,        # 用户记忆（可能为空）
                "dynamic_context": str,    # 时间 + 用户邮箱 + 附件状态
            }
        """
        # 系统提示词：base_prompt + reply_rules
        system_prompt = base_prompt
        if reply_rules:
            system_prompt = f"{base_prompt}\n\n{reply_rules}"

        # 用户记忆
        user_memory = memories or ""

        # 动态上下文：当前时间 + 用户信息 + 附件状态
        dynamic_parts = [f"## 当前时间\n{timestamp}"]
        if user_info and user_info.get("email"):
            dynamic_parts.append(f"## 用户\n{user_info['email']}")

        # 附件状态：让 AI 知道当前有哪些文件可用
        if attachments:
            file_list = "\n".join(
                f"- {a['filename']} (id: {a.get('file_id', '')})" for a in attachments
            )
            dynamic_parts.append(f"## 当前会话文件\n{file_list}")
        else:
            dynamic_parts.append("## 当前会话文件\n（无，用户尚未上传文件）")

        dynamic_context = "\n\n".join(dynamic_parts)

        return {
            "system_prompt": system_prompt,
            "user_memory": user_memory,
            "dynamic_context": dynamic_context,
        }

    def build_system_prompt(
        self,
        base_prompt: str,        # 基础系统提示，来自 EngineConfig.system_prompt
        user_info: dict,         # {"email": str}，后续可能扩展 name 等
        memories: str,           # 跨会话记忆文本（空串表示无记忆）
        timestamp: str,          # ISO 格式时间戳
        reply_rules: str = "",   # 新增参数：回复规范
    ) -> str:
        """构建系统提示词。

        用 base_prompt 开头，依次追加回复规范、当前时间、用户信息和记忆等部分，
        各部分用 \n\n 分隔。

        Args:
            base_prompt: 基础系统提示
            user_info: 用户信息字典，包含 email 等字段
            memories: 跨会话记忆文本，空串表示无记忆
            timestamp: ISO 格式时间戳
            reply_rules: 回复规范文本，空串表示无规范

        Returns:
            构建好的系统提示词文本
        """
        parts = [base_prompt]

        # 在 base_prompt 之后、当前时间之前插入回复规范
        if reply_rules:
            parts.append(reply_rules)

        # 追加当前时间
        parts.append(f"## 当前时间\n{timestamp}")

        # 如果有 email，追加用户信息
        if user_info and user_info.get("email"):
            parts.append(f"## 用户\n{user_info['email']}")

        # 如果有记忆，追加用户记忆
        if memories:
            parts.append(f"## 用户记忆\n{memories}")

        return "\n\n".join(parts)

    async def compress_history(
        self,
        history: list[dict],     # OpenAI 格式的消息列表
        max_tokens: int = 50000, # 触发压缩的阈值
        llm_chat_stream=None,    # llm_bridge.client.chat_stream（用于 LLM 汇总）
    ) -> list[dict]:
        """压缩对话历史。

        如果总 token 数未超过限制，直接返回原始历史。
        如果超过，取最旧的 1/3 消息进行 LLM 汇总或用固定文本代替，
        返回摘要 + 剩余消息。

        Args:
            history: OpenAI 格式的消息列表 [{"role": "user"/"assistant", "content": "..."}]
            max_tokens: token 数阈值
            llm_chat_stream: 可选的 LLM 流式对话接口，用于生成摘要

        Returns:
            压缩后的消息列表
        """
        # 估算 token 数：简单近似
        total_tokens = sum(len(m.get("content") or "") for m in history) // 4

        # 如果未超过限制，直接返回
        if total_tokens < max_tokens:
            return history

        # 需要压缩：取最旧的 1/3 条消息
        compress_count = len(history) // 3
        if compress_count == 0:
            compress_count = 1

        oldest_messages = history[:compress_count]
        remaining_messages = history[compress_count:]

        # 生成摘要
        if llm_chat_stream:
            # 调用 LLM 汇总
            summary = await self._summarize_with_llm(oldest_messages, llm_chat_stream)
        else:
            # 直接用固定文本
            summary = "[已压缩的早期对话]"

        # 返回 [摘要系统消息] + 剩余消息
        result = [
            {"role": "system", "content": f"早期对话摘要：{summary}"}
        ] + remaining_messages

        return result

    async def _summarize_with_llm(self, messages: list[dict], llm_chat_stream) -> str:
        """使用 LLM 汇总一组消息。复用 llm_bridge 的流式接口收集非流式结果。

        Args:
            messages: 要汇总的消息列表
            llm_chat_stream: lm_bridge.client.chat_stream

        Returns:
            汇总文本
        """
        dialog_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in messages
        )
        prompt = f"请用 bullet points 汇总以下对话的核心内容（<100词），中英文均可\n\n{dialog_text}"

        full_response = ""
        import json as _json
        async for event_str in llm_chat_stream(
            email="system",
            session_id="summarize",
            message=prompt,
            history=[],
            system_prompt="你是一个对话摘要助手。",
        ):
            # 从 SSE data: 事件中提取文本 token
            for line in event_str.split("\n"):
                if line.startswith("data: ") and "[DONE]" not in line:
                    try:
                        payload = _json.loads(line[6:])
                        token = (
                            payload.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        full_response += token
                    except Exception:
                        pass

        return full_response.strip() or "[已压缩的早期对话]"
