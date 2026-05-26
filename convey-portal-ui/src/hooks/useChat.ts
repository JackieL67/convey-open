import { useState, useCallback, useRef } from 'react';
import type { Message } from '@/types';

export function useChat(
  email: string | null,
  sessionId: string | null,
  authHeaders: () => Record<string, string>,
  handleAuthError: () => void,
) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const loadConversation = useCallback(async (sid: string) => {
    if (!email) return;
    try {
      const resp = await fetch(
        `/api/conversations/${encodeURIComponent(email)}/${encodeURIComponent(sid)}`,
        { headers: { ...authHeaders() } }
      );
      if (resp.status === 401) {
        handleAuthError();
        return;
      }
      if (resp.ok) {
        const data = await resp.json();
        const loaded: Message[] = (data.messages || []).map((m: Record<string, unknown>, i: number) => ({
          id: (m.id as string) || `msg_${i}`,
          role: (m.role as 'user' | 'assistant'),
          content: (m.content as string) || '',
          timestamp: (m.timestamp as number) || 0,
          status: (m.metadata as Record<string, unknown>)?.status as Message['status'],
          reply_to: (m.metadata as Record<string, unknown>)?.reply_to as string,
          thinking_time: (m.metadata as Record<string, unknown>)?.thinking_time as number,
          attachments: (m.metadata as Record<string, unknown>)?.attachments as Message['attachments'],
          metadata: m.metadata as Record<string, unknown>,
        }));
        setMessages(loaded);

        // Check for pending messages that need retry
        const hasPending = loaded.some(m => m.status === 'pending' || m.status === 'processing');
        if (hasPending) {
          // Will be handled by auto-retry logic in Phase 6
        }
      }
    } catch {
      // network error, connection monitor will show banner
    }
  }, [email, authHeaders, handleAuthError]);

  const sendMessage = useCallback(async (text: string, attachments?: File[]) => {
    if (!email || !sessionId || !text.trim()) return;

    const now = Date.now();
    const userMsg: Message = {
      id: `msg_${now}`,
      role: 'user',
      content: text,
      timestamp: now / 1000,
      status: 'pending',
    };

    setMessages(prev => [...prev, userMsg]);
    setIsStreaming(true);

    // Create AI message placeholder
    const aiMsgId = `msg_${now + 1}`;
    const aiMsg: Message = {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      timestamp: now / 1000,
      status: 'processing',
      reply_to: text.length > 20 ? text.slice(0, 20) + '...' : text,
    };
    setMessages(prev => [...prev, aiMsg]);

    // AbortController for stop
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      // Upload attachments first if any
      let attachmentData: Record<string, unknown>[] = [];
      if (attachments && attachments.length > 0) {
        for (const file of attachments) {
          const formData = new FormData();
          formData.append('file', file);
          const uploadResp = await fetch('/api/upload', {
            method: 'POST',
            headers: authHeaders(),
            body: formData,
          });
          if (uploadResp.status === 401) { handleAuthError(); return; }
          if (uploadResp.ok) {
            const uploadData = await uploadResp.json();
            attachmentData.push({
              id: uploadData.file_id,
              filename: file.name,
              url: uploadData.url,
              type: file.type,
              size: file.size,
            });
          }
        }
      }

      // Send message with SSE
      const body: Record<string, unknown> = {
        email,
        message: text,
        session_id: sessionId,
      };
      if (attachmentData.length > 0) {
        body.attachments = attachmentData;
      }

      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          ...authHeaders(),
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (resp.status === 401) { handleAuthError(); return; }
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        setMessages(prev => prev.map(m =>
          m.id === aiMsgId ? { ...m, status: 'failed', content: '' } : m
        ));
        setIsStreaming(false);
        return;
      }

      // Parse SSE stream
      const reader = resp.body?.getReader();
      if (!reader) { setIsStreaming(false); return; }

      const decoder = new TextDecoder();
      let buffer = '';
      let currentEvent = '';
      let thinkingStart = 0;
      let fullContent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event:')) {
            currentEvent = line.slice(6).trim();
          } else if (line.startsWith('data:')) {
            const dataStr = line.slice(5).trim();

            if (currentEvent === 'thinking') {
              thinkingStart = Date.now();
            } else if (currentEvent === 'reasoning') {
              // Reasoning section — append to AI message
              try {
                const parsed = JSON.parse(dataStr);
                setMessages(prev => prev.map(m =>
                  m.id === aiMsgId ? { ...m, metadata: { ...m.metadata, reasoning: (m.metadata?.reasoning || '') + parsed.content } } : m
                ));
              } catch { /* ignore */ }
            } else if (currentEvent === 'tool') {
              try {
                const parsed = JSON.parse(dataStr);
                setMessages(prev => prev.map(m =>
                  m.id === aiMsgId ? { ...m, metadata: { ...m.metadata, toolCall: parsed } } : m
                ));
              } catch { /* ignore */ }
            } else if (currentEvent === 'error') {
              try {
                const parsed = JSON.parse(dataStr);
                setMessages(prev => prev.map(m =>
                  m.id === aiMsgId ? { ...m, status: 'failed', metadata: { ...m.metadata, error: parsed.message } } : m
                ));
              } catch { /* ignore */ }
            } else if (currentEvent === 'done') {
              const thinkDuration = thinkingStart ? (Date.now() - thinkingStart) / 1000 : undefined;
              setMessages(prev => prev.map(m =>
                m.id === aiMsgId ? { ...m, status: 'completed', thinking_time: thinkDuration, content: fullContent || m.content } : m
              ));
            } else if (dataStr === '[DONE]') {
              // Stream complete
            } else {
              // Text token
              try {
                const parsed = JSON.parse(dataStr);
                const token = parsed.choices?.[0]?.delta?.content || parsed.token || '';
                if (token) {
                  fullContent += token;
                  setMessages(prev => prev.map(m =>
                    m.id === aiMsgId ? { ...m, content: fullContent } : m
                  ));
                }
              } catch {
                // Raw text token
                if (dataStr && dataStr !== '[DONE]') {
                  fullContent += dataStr;
                  setMessages(prev => prev.map(m =>
                    m.id === aiMsgId ? { ...m, content: fullContent } : m
                  ));
                }
              }
            }
            currentEvent = '';
          }
        }
      }

      // Finalize: if no done event received, mark completed anyway
      setMessages(prev => prev.map(m =>
        m.id === aiMsgId && m.status === 'processing'
          ? { ...m, status: 'completed', content: fullContent || m.content }
          : m
      ));
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        // User clicked stop
        setMessages(prev => prev.map(m =>
          m.id === aiMsgId ? { ...m, status: 'cancelled' } : m
        ));
      } else {
        setMessages(prev => prev.map(m =>
          m.id === aiMsgId ? { ...m, status: 'failed' } : m
        ));
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }, [email, sessionId, authHeaders, handleAuthError]);

  const stopStreaming = useCallback(() => {
    abortControllerRef.current?.abort();
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return {
    messages,
    isStreaming,
    sendMessage,
    stopStreaming,
    loadConversation,
    clearMessages,
  };
}
