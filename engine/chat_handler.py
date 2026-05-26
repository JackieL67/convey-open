"""
Conversation Engine · 对话处理器

处理消息收发：加载历史 → 调 Bridge → 保存回复。
支持 SSE 流式输出。
"""

import json
import logging
import asyncio
from typing import AsyncIterator, Optional, Callable

from engine.db import EngineDB
from engine.config import EngineConfig

logger = logging.getLogger(__name__)


class ChatHandler:
    """对话处理器。"""

    def __init__(
        self,
        db: EngineDB,
        config: EngineConfig,
        memory_client=None,
        llm_chat_stream: Optional[Callable] = None,
        tool_executor=None,
    ):
        self.db = db
        self.config = config
        self.memory_client = memory_client
        self.llm_chat_stream = llm_chat_stream
        self.tool_executor = tool_executor

    async def chat(
        self,
        email: str,
        session_id: str,
        message: str,
    ) -> dict:
        """
        发送消息并获取回复（同步）。

        Args:
            email: 用户邮箱
            session_id: 会话 ID
            message: 用户消息

        Returns:
            { "reply": "...", "message_id": int }
        """
        # 1. 保存用户消息（status: pending）
        user_msg_id = self.db.save_message(session_id, "user", message, metadata={"status": "pending"})

        # 2. 加载历史
        history = self.db.get_conversation_history(
            session_id, limit=self.config.max_history_messages
        )

        # 3. 构建 system_prompt（可选注入记忆）
        system_prompt = self.config.system_prompt
        if self.memory_client and message:
            try:
                memories = await self.memory_client.get(email, message)
                if memories:
                    system_prompt = system_prompt + "\n\n" + memories
            except Exception as e:
                logger.warning("Failed to inject memory: %s", e)

        # 4. 调用 LLM Bridge（同步模式）
        self.db.update_message_status(user_msg_id, "processing")
        reply_content = ""
        try:
            if self.llm_chat_stream:
                # 注意：在 chat() 中需要同步调用异步生成器
                full_reply = ""
                async for event_str in self.llm_chat_stream(
                    email=email,
                    session_id=session_id,
                    message=message,
                    history=history[:-1],  # 排除刚保存的用户消息
                    system_prompt=system_prompt,
                    attachments=None,
                    options=None,
                    config=None,
                ):
                    # 解析 SSE 事件，提取文本内容
                    if "data: " in event_str:
                        data_part = event_str.split("data: ", 1)[1].strip()
                        try:
                            payload = json.loads(data_part)
                            if "choices" in payload:
                                token = payload["choices"][0].get("delta", {}).get("content", "")
                                full_reply += token
                        except json.JSONDecodeError:
                            pass
                reply_content = full_reply
            else:
                raise RuntimeError("llm_chat_stream not configured")
            self.db.update_message_status(user_msg_id, "completed")
        except Exception as e:
            logger.error("LLM Bridge chat failed: %s", e)
            # 用户消息本身已成功发送，保持 completed
            self.db.update_message_status(user_msg_id, "completed")
            reply_content = "AI 回复出错，请重试"

        # 5. 保存 AI 回复
        assistant_msg_id = self.db.save_message(session_id, "assistant", reply_content)

        # 6. 异步更新记忆（不阻塞）
        if self.memory_client:
            try:
                all_messages = self.db.get_messages(session_id)
                asyncio.create_task(self.memory_client.update(email, all_messages))
            except Exception as e:
                logger.warning("Failed to update memory: %s", e)

        return {
            "reply": reply_content,
            "user_message_id": user_msg_id,
            "assistant_message_id": assistant_msg_id,
        }

    async def chat_stream(
        self,
        email: str,
        session_id: str,
        message: str,
        options: dict = None,
        attachments: list = None,
    ) -> AsyncIterator[str]:
        """
        发送消息并获取 SSE 流式回复（V3 结构化事件）。

        SSE 事件类型:
            data: {"choices":[...]}  (text 事件，兼容旧 Portal)
            event: reasoning         (推理过程)
            event: tool              (工具调用 start/result)
            event: done              (完成 + 元数据)
            data: [DONE]              (结束标记，兼容旧前端)
        """
        # 1. 保存用户消息（原始文本 + 附件存 metadata，初始状态 processing）
        user_metadata = {"status": "processing"}
        if attachments:
            user_metadata["attachments"] = [
                {"file_id": a.get("file_id", ""), "filename": a.get("filename", ""),
                 "content_type": a.get("content_type", ""), "url": a.get("url", "")}
                for a in attachments
            ]
        user_msg_id = self.db.save_message(session_id, "user", message, metadata=user_metadata)

        # 2. 加载历史（含 metadata，注入附件 URL 给 AI）
        raw_messages = self.db.get_messages(
            session_id, limit=self.config.max_history_messages
        )

        # 构建 LLM 格式的历史，注入附件 URL
        history = []
        for m in raw_messages:
            content = m["content"]
            meta = m.get("metadata", {})
            if isinstance(meta, str):
                import json as _json
                try: meta = _json.loads(meta)
                except: meta = {}
            if m["role"] == "user" and meta.get("attachments"):
                attach_lines = []
                for att in meta["attachments"]:
                    # Prefer the URL saved at upload time (set by server with CONVEY_PUBLIC_URL)
                    file_url = att.get("url") or f"{self.config.portal_url}/api/files/{att['file_id']}"
                    ct = att.get("content_type", "")
                    if ct.startswith("image/"):
                        attach_lines.append(f"[用户上传了图片: {att['filename']} (file_id: {att['file_id']}), URL: {file_url}]")
                    else:
                        attach_lines.append(f"[用户上传了文件: {att['filename']} (file_id: {att['file_id']}), URL: {file_url}]")
                if attach_lines:
                    content = "\n".join(attach_lines) + ("\n" + content if content else "")
            history.append({"role": m["role"], "content": content})

        # 3. 构建当前消息（注入附件信息，与历史消息格式一致）
        current_content = message
        if attachments:
            current_attach_lines = []
            for att in attachments:
                file_url = att.get("url") or f"{self.config.portal_url}/api/files/{att['file_id']}"
                ct = att.get("content_type", "")
                if ct.startswith("image/"):
                    current_attach_lines.append(
                        f"[用户上传了图片: {att['filename']} (file_id: {att['file_id']}), URL: {file_url}]"
                    )
                else:
                    current_attach_lines.append(
                        f"[用户上传了文件: {att['filename']} (file_id: {att['file_id']}), URL: {file_url}]"
                    )
            if current_attach_lines:
                current_content = "\n".join(current_attach_lines) + ("\n" + current_content if current_content else "")

        # 4. 构建 system_prompt 和 system_parts（ContextManager 动态注入）
        from datetime import datetime
        system_prompt = self.config.system_prompt
        system_parts = None
        try:
            from data.context.manager import ContextManager
            from crm import crm as crm_instance
            
            cm = ContextManager()
            memories = ""
            if self.memory_client and message:
                try:
                    memories = await self.memory_client.get(email, message)
                except Exception as e:
                    logger.warning("Failed to inject memory: %s", e)
            
            # 从 CRM 获取用户自定义 system_prompt 和 reply_rules
            base_prompt = crm_instance.get_system_prompt(email)
            reply_rules = crm_instance.get_reply_rules(email)
            
            # 构建结构化系统部分（含附件状态）
            system_parts = cm.build_system_parts(
                base_prompt=base_prompt,
                user_info={"email": email},
                memories=memories,
                timestamp=datetime.utcnow().isoformat(),
                reply_rules=reply_rules,
                attachments=attachments,  # AI 感知附件状态
            )
            
            # 构建完整 system_prompt（兼容旧 API，用于某些需要单个 system 消息的地方）
            system_prompt = cm.build_system_prompt(
                base_prompt=base_prompt,
                user_info={"email": email},
                memories=memories,
                timestamp=datetime.utcnow().isoformat(),
                reply_rules=reply_rules,
            )
        except Exception as e:
            logger.warning("ContextManager not available, using static prompt: %s", e)
            system_prompt = self.config.system_prompt

        # 5. 映射 options：reasoning_level → reasoning_effort
        llm_options = {}
        if options:
            # Portal 传来 reasoning_level(high/max) → llm-bridge 需要 reasoning_effort
            reasoning_level = options.get("reasoning_level", "high")
            if reasoning_level in ("high", "max"):
                llm_options["reasoning_effort"] = reasoning_level
            if "reply_style" in options:
                llm_options["reply_style"] = options["reply_style"]
            if "model" in options:
                llm_options["model"] = options["model"]

        # 6. 通知 Portal：AI 开始思考 + 更新状态为 processing
        yield "event: thinking\ndata: {}\n\n"
        self.db.update_message_status(user_msg_id, "processing")

        # 7. 结构化流式调用 LLM（工具循环 + 心跳，最多 MAX_TOOL_ROUNDS 轮工具调用）
        #
        # 双路径设计：
        #   - 如果配置了 llm_client + tool_executor → 走 Tool Loop（新路径）
        #   - 否则 → 走旧 llm_chat_stream 路径（兜底，确保向后兼容）
        #
        # Tool Loop SSE 事件顺序（每轮）：
        #   reasoning → tool_call(s) → tool_result(s) → [下一轮] → text → done → [DONE]
        HEARTBEAT_INTERVAL = 15
        MAX_TOOL_ROUNDS = 30
        full_reply = ""
        full_reasoning = ""
        assistant_msg_id = None
        save_counter = 0
        final_usage = None
        stream_completed = False

        try:
            # 上下文压缩（两条路径共用）
            try:
                from data.context.manager import ContextManager
                ctx = ContextManager()
                compressed = await ctx.compress_history(
                    history[:-1],                # 排除当前 user 消息，避免与 message 重复
                    max_tokens=50000,
                    llm_chat_stream=self.llm_chat_stream,
                )
            except Exception:
                compressed = history[:-1]

            # ⚠️ 关键：在 tool loop 之前把当前 user 消息追加到 compressed
            # 这样第二轮起 message="" 也依赖 history 末尾的 user 消息
            # DS V4 协议要求: [user] → [assistant(tool_calls)] → [tool result]
            compressed.append({"role": "user", "content": current_content})

            if self.tool_executor:
                # ============================================================
                # Path A: Tool Loop — 通过 chat_stream_with_tools 循环
                # ============================================================
                from util.tools import get_registry
                from llm_bridge.client import chat_stream_with_tools

                tools = get_registry().get_definitions()
                tool_round = 0

                while tool_round < MAX_TOOL_ROUNDS:
                    tool_round += 1

                    # 调 Bridge（含 tools 参数）
                    stream = chat_stream_with_tools(
                        email=email,
                        session_id=session_id,
                        message="",  # user 消息已在 compressed 末尾
                        history=compressed,
                        system_prompt=system_prompt,
                        attachments=attachments,
                        options=llm_options or None,
                        tools=tools,
                    )

                    done_data = None
                    ait = stream.__aiter__()
                    while True:
                        try:
                            event_str = await asyncio.wait_for(
                                ait.__anext__(), timeout=HEARTBEAT_INTERVAL
                            )
                        except asyncio.TimeoutError:
                            yield "event: heartbeat\ndata: {}\n\n"
                            continue
                        except StopAsyncIteration:
                            break

                        yield event_str  # 透传所有 SSE 事件

                        # 解析 done 事件
                        if event_str.startswith("event: done"):
                            try:
                                data_part = event_str.split("\ndata: ", 1)[1].split("\n")[0].strip()
                                done_data = json.loads(data_part)
                                if done_data.get("usage"):
                                    final_usage = done_data["usage"]
                                if done_data.get("reasoning"):
                                    full_reasoning = done_data["reasoning"]
                            except Exception:
                                pass

                        # DB 持久化（提取 content token）
                        if "data: " in event_str:
                            for line_str in event_str.split("\n"):
                                if not line_str.startswith("data: "):
                                    continue
                                data_part = line_str[6:].strip()
                                if data_part == "[DONE]" or data_part.startswith("event:"):
                                    continue
                                try:
                                    payload = json.loads(data_part)
                                    if "choices" in payload:
                                        token = payload["choices"][0].get("delta", {}).get("content", "")
                                        if token:
                                            full_reply += token
                                            if assistant_msg_id is None:
                                                assistant_msg_id = self.db.save_message(
                                                    session_id, "assistant", full_reply,
                                                    metadata={"status": "processing"},
                                                )
                                            else:
                                                save_counter += 1
                                                if save_counter % 5 == 0:
                                                    self.db.update_message_content(
                                                        assistant_msg_id, full_reply
                                                    )
                                    elif payload.get("type") == "reasoning":
                                        full_reasoning += payload.get("content", "")
                                except json.JSONDecodeError:
                                    pass

                    # done 事件处理完毕
                    if done_data is None:
                        stream_completed = True
                        break

                    finish = done_data.get("finish_reason", "stop")

                    if finish == "stop":
                        stream_completed = True
                        break

                    if finish == "tool_calls":
                        raw_tool_calls = done_data.get("tool_calls", [])

                        # ① 发 tool_call SSE 事件给前端
                        parsed_tc = []
                        for tc in raw_tool_calls:
                            try:
                                args = json.loads(tc["function"]["arguments"])
                            except (json.JSONDecodeError, KeyError, TypeError):
                                args = {}
                            parsed_tc.append({
                                "id": tc.get("id", ""),
                                "name": tc["function"]["name"],
                                "args": args,
                            })
                            tc_sse = json.dumps({
                                "type": "tool_call",
                                "name": tc["function"]["name"],
                                "args": args,
                            }, ensure_ascii=False)
                            yield f"event: tool_call\ndata: {tc_sse}\n\n"

                        if not parsed_tc:
                            stream_completed = True
                            break

                        # ② 并发执行工具
                        logger.info(
                            "Tool loop round %d: executing %d tool(s): %s",
                            tool_round, len(parsed_tc),
                            [tc["name"] for tc in parsed_tc],
                        )
                        results = await self.tool_executor.execute_all(parsed_tc)

                        # ③ 发 tool_result SSE 事件
                        for r in results:
                            cv = r.get("content", "")
                            if isinstance(cv, dict):
                                content_str = cv.get("content", str(cv))
                            else:
                                content_str = str(cv) if cv else ""
                            tr_sse = json.dumps({
                                "type": "tool_result",
                                "name": r.get("name", ""),
                                "content": content_str,
                                "elapsed_ms": r.get("elapsed_ms", 0),
                            }, ensure_ascii=False)
                            yield f"event: tool_result\ndata: {tr_sse}\n\n"

                        # ④ 回填到 history（供下一轮）
                        # DS V4 thinking 模式要求必须回传 reasoning_content
                        assistant_msg = {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": raw_tool_calls,
                        }
                        reasoning_content = done_data.get("reasoning", "")
                        if reasoning_content:
                            assistant_msg["reasoning_content"] = reasoning_content
                        compressed.append(assistant_msg)
                        for tc_info, r in zip(parsed_tc, results):
                            cv = r.get("content", "")
                            if isinstance(cv, dict):
                                content_str = cv.get("content", str(cv))
                            else:
                                content_str = str(cv) if cv else ""
                            compressed.append({
                                "role": "tool",
                                "tool_call_id": tc_info["id"],
                                "content": content_str,
                            })

                        continue  # 下一轮工具循环

                    # 其他 finish_reason：结束
                    stream_completed = True
                    break

            else:
                # ============================================================
                # Path B: Legacy — 原有 llm_chat_stream 路径（向后兼容）
                # ============================================================
                if not self.llm_chat_stream:
                    raise RuntimeError("llm_chat_stream not configured")

                ait = self.llm_chat_stream(
                    email=email,
                    session_id=session_id,
                    message=current_content,
                    history=compressed,
                    system_prompt=system_prompt,
                    attachments=attachments,
                    options=llm_options or None,
                    config=None,
                ).__aiter__()

                while True:
                    try:
                        event_str = await asyncio.wait_for(ait.__anext__(), timeout=HEARTBEAT_INTERVAL)
                    except asyncio.TimeoutError:
                        yield "event: heartbeat\ndata: {}\n\n"
                        continue
                    except StopAsyncIteration:
                        break

                    yield event_str

                    if "data: " in event_str:
                        lines = event_str.split("\n")
                        for line in lines:
                            if line.startswith("data: "):
                                data_part = line[6:].strip()
                                if data_part == "[DONE]":
                                    continue
                                try:
                                    payload = json.loads(data_part)
                                    if "choices" in payload:
                                        token = payload["choices"][0].get("delta", {}).get("content", "")
                                        if token:
                                            full_reply += token
                                            if assistant_msg_id is None:
                                                assistant_msg_id = self.db.save_message(
                                                    session_id, "assistant", full_reply,
                                                    metadata={"status": "processing"},
                                                )
                                            else:
                                                save_counter += 1
                                                if save_counter % 5 == 0:
                                                    self.db.update_message_content(assistant_msg_id, full_reply)
                                    elif "type" in payload and payload["type"] == "reasoning":
                                        token = payload.get("content", "")
                                        if token:
                                            full_reasoning += token
                                    elif "type" in payload and payload["type"] == "done":
                                        if payload.get("usage"):
                                            final_usage = payload["usage"]
                                        if payload.get("reasoning"):
                                            full_reasoning = payload["reasoning"]
                                except json.JSONDecodeError:
                                    pass

                stream_completed = True

        except asyncio.CancelledError:
            logger.info("Stream cancelled by client (session=%s)", session_id)
            self.db.update_message_status(user_msg_id, "cancelled")
            sse_data = json.dumps(
                {"type": "error", "message": "连接已断开"},
                ensure_ascii=False,
            )
            yield f"event: error\ndata: {sse_data}\n\n"
            return

        except Exception as e:
            logger.error("LLM Bridge stream failed: %s", e)
            self.db.update_message_status(user_msg_id, "completed")
            error_reply = "AI 回复出错，请重试"
            self.db.save_message(session_id, "assistant", error_reply,
                                 metadata={"status": "failed", "error": str(e)})
            sse_data = json.dumps(
                {"type": "error", "message": "AI 回复出错，请重试"},
                ensure_ascii=False,
            )
            yield f"event: error\ndata: {sse_data}\n\n"

        # 8. 保存完整 AI 回复 + 更新用户消息状态
        if stream_completed:
            self.db.update_message_status(user_msg_id, "completed")
            if assistant_msg_id and full_reply:
                # 最终写入：补全最后一段内容 + 更新 metadata
                self.db.update_message_content(assistant_msg_id, full_reply)
                msg_metadata = {
                    "status": "completed",
                    "options": options or {},
                }
                if final_usage:
                    msg_metadata["usage"] = final_usage
                if full_reasoning:
                    msg_metadata["reasoning"] = full_reasoning
                self.db.update_message_status(assistant_msg_id, "completed")
                import json as _json
                with self.db._conn() as conn:
                    conn.execute(
                        "UPDATE messages SET metadata = ? WHERE id = ?",
                        (_json.dumps(msg_metadata, ensure_ascii=False), assistant_msg_id),
                    )
            elif assistant_msg_id and not full_reply:
                # 有占位消息但无内容 → 标记为 cancelled
                self.db.update_message_status(assistant_msg_id, "cancelled")
            
            # 9. 保存 context 快照到 CRM（使用新的结构化格式）
            try:
                from crm import crm as _crm_instance
                from datetime import datetime as _dt
                
                # 生成估算 token 数的辅助函数
                def estimate_tokens(text: str) -> int:
                    return max(1, len(text) // 4) if text else 0
                
                # 新快照格式：分离系统提示词、用户记忆、动态上下文
                snapshot = {
                    "system_prompt": system_parts.get("system_prompt", "") if system_parts else system_prompt,
                    "user_memory": system_parts.get("user_memory", "") if system_parts else "",
                    "dynamic_context": system_parts.get("dynamic_context", "") if system_parts else "",
                    "history": compressed[:-1] if compressed else history[:-1],  # 排除刚保存的用户消息
                    "current_message": current_content,
                    "timestamp": _dt.utcnow().isoformat(),
                    "history_count": len(compressed) - 1 if compressed else len(history) - 1,
                }
                
                # 估算各部分 token
                snapshot["system_token_estimate"] = estimate_tokens(snapshot["system_prompt"])
                snapshot["user_memory_token_estimate"] = estimate_tokens(snapshot["user_memory"])
                snapshot["dynamic_context_token_estimate"] = estimate_tokens(snapshot["dynamic_context"])
                snapshot["history_token_estimate"] = sum(
                    estimate_tokens(m.get("content", "")) for m in snapshot["history"]
                )
                snapshot["current_token_estimate"] = estimate_tokens(current_content)
                snapshot["total_token_estimate"] = (
                    snapshot["system_token_estimate"]
                    + snapshot["user_memory_token_estimate"]
                    + snapshot["dynamic_context_token_estimate"]
                    + snapshot["history_token_estimate"]
                    + snapshot["current_token_estimate"]
                )
                
                _crm_instance.save_context_snapshot(email, snapshot)
            except Exception as e:
                logger.warning("Failed to save context snapshot: %s", e)

        # 9. 异步更新记忆（不阻塞）
        if self.memory_client:
            try:
                all_messages = self.db.get_messages(session_id)
                asyncio.create_task(self.memory_client.update(email, all_messages))
            except Exception as e:
                logger.warning("Failed to update memory: %s", e)

    async def get_agent_status(self) -> dict:
        """获取 Agent 状态。"""
        # 返回空数据（不依赖 router）
        return {
            "status": "ok",
            "agent": {},
        }

    async def get_tools(self) -> dict:
        """获取可用工具列表。"""
        # 返回空数据（不依赖 router）
        return {
            "tools": [],
            "error": "Tool discovery not available",
        }

    def get_token_stats(self, session_id: str = None) -> dict:
        """获取 Token 使用统计。"""
        # MVP: 从 Engine DB 统计消息数
        # 未来可对接 Bridge 获取精确 token 数据
        result = self.db.get_message_counts(session_id)
        result["note"] = "Token-level statistics require Bridge integration (ENGINE-02)"
        return result

    async def get_context_preview(
        self, email: str, session_id: str, message: str,
        attachments: list = None,
    ) -> dict:
        """
        获取当前会话即将发给 LLM 的完整上下文预览。

        这个方法复用 chat_stream 的逻辑来构建上下文，但不实际发消息。

        Returns:
            {
                "system_prompt": str,            # 完整 system_prompt
                "history": list,                 # 历史消息预览列表
                "current_message": str,          # 当前用户消息
                "history_count": int,            # 历史消息条数
                "history_token_estimate": int,   # 历史估算 tokens
                "total_token_estimate": int,     # 总估算 tokens
            }
        """
        # 1. 加载完整历史
        raw_messages = self.db.get_messages(
            session_id, limit=self.config.max_history_messages
        )

        # 2. 构建 LLM 格式的历史消息预览
        history = []
        for m in raw_messages:
            content = m["content"]
            meta = m.get("metadata", {})
            if isinstance(meta, str):
                import json as _json
                try:
                    meta = _json.loads(meta)
                except:
                    meta = {}
            if m["role"] == "user" and meta.get("attachments"):
                attach_lines = []
                for att in meta["attachments"]:
                    file_url = att.get("url") or f"{self.config.portal_url}/api/files/{att['file_id']}"
                    ct = att.get("content_type", "")
                    if ct.startswith("image/"):
                        attach_lines.append(f"[用户上传了图片: {att['filename']} (file_id: {att['file_id']}), URL: {file_url}]")
                    else:
                        attach_lines.append(f"[用户上传了文件: {att['filename']} (file_id: {att['file_id']}), URL: {file_url}]")
                if attach_lines:
                    content = "\n".join(attach_lines) + ("\n" + content if content else "")
            
            # 为预览截断内容（前200字符）
            preview_content = content[:200] + ("..." if len(content) > 200 else "")
            history.append({
                "role": m["role"],
                "content": preview_content,
                "full_length": len(content),
            })

        # 3. 构建 system_prompt 和 system_parts（新结构化格式）
        system_prompt = self.config.system_prompt
        system_parts = None
        try:
            from datetime import datetime
            from data.context.manager import ContextManager
            from crm import crm as crm_instance

            cm = ContextManager()
            memories = ""
            if self.memory_client and message:
                try:
                    memories = await self.memory_client.get(email, message)
                except Exception as e:
                    logger.warning("Failed to inject memory: %s", e)

            base_prompt = crm_instance.get_system_prompt(email)
            reply_rules = crm_instance.get_reply_rules(email)

            # 构建结构化系统部分（含附件状态）
            system_parts = cm.build_system_parts(
                base_prompt=base_prompt,
                user_info={"email": email},
                memories=memories,
                timestamp=datetime.utcnow().isoformat(),
                reply_rules=reply_rules,
                attachments=attachments,  # AI 感知附件状态
            )

            # 构建完整 system_prompt（兼容旧 API）
            system_prompt = cm.build_system_prompt(
                base_prompt=base_prompt,
                user_info={"email": email},
                memories=memories,
                timestamp=datetime.utcnow().isoformat(),
                reply_rules=reply_rules,
            )
        except Exception as e:
            logger.warning("ContextManager not available, using static prompt: %s", e)
            system_prompt = self.config.system_prompt

        # 4. 估算 token 数（简单估算：假设平均 4 字符 = 1 token）
        def estimate_tokens(text: str) -> int:
            return max(1, len(text) // 4) if text else 0

        history_tokens = sum(estimate_tokens(h["content"]) for h in history)
        current_tokens = estimate_tokens(message)
        
        # 使用 system_parts 的各部分分别估算 token
        if system_parts:
            system_tokens = estimate_tokens(system_parts["system_prompt"])
            user_memory_tokens = estimate_tokens(system_parts["user_memory"])
            dynamic_context_tokens = estimate_tokens(system_parts["dynamic_context"])
            total_system_tokens = system_tokens + user_memory_tokens + dynamic_context_tokens
        else:
            system_tokens = estimate_tokens(system_prompt)
            user_memory_tokens = 0
            dynamic_context_tokens = 0
            total_system_tokens = system_tokens
        
        total_tokens = total_system_tokens + history_tokens + current_tokens

        # 返回新格式（包含拆分的系统提示词部分 + 附件/工具状态）
        from util.tools import get_registry
        tool_defs = get_registry().get_definitions()
        active_tools = [t["function"]["name"] for t in tool_defs]
        result = {
            "system_prompt": system_parts.get("system_prompt", "") if system_parts else system_prompt,
            "user_memory": system_parts.get("user_memory", "") if system_parts else "",
            "dynamic_context": system_parts.get("dynamic_context", "") if system_parts else "",
            "history": history,
            "current_message": message,
            "history_count": len(history),
            "history_token_estimate": history_tokens,
            "system_token_estimate": system_tokens,
            "user_memory_token_estimate": user_memory_tokens,
            "dynamic_context_token_estimate": dynamic_context_tokens,
            "current_token_estimate": current_tokens,
            "total_token_estimate": total_tokens,
            "attachments_count": len(attachments) if attachments else 0,
            "attachments": attachments or [],
            "active_tools": active_tools,
            "tools_count": len(active_tools),
        }
        return result
