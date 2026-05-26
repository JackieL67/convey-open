import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import type { Message, QuickReply } from '@/types';
import TopBar from '@/components/TopBar';
import SessionPanel from '@/components/SessionPanel';
import MessageList from '@/components/MessageList';
import QuickReplyStrip from '@/components/QuickReplyStrip';
import InputBar from '@/components/InputBar';
import SettingsPanel, { loadSettings, type ConveySettings } from '@/components/SettingsPanel';
import SystemPromptEditor from '@/components/SystemPromptEditor';
import ContextPreview from '@/components/ContextPreview';
import AboutPanel from '@/components/AboutPanel';
import { useMobile } from '@/hooks/useMobile';

interface ChatScreenProps {
  email: string;
  authHeaders: () => Record<string, string>;
  authFetch: (url: string, options?: RequestInit) => Promise<Response>;
  handleAuthError: () => void;
  onLogout: () => void;
}

// Minimal inline hooks (will be extracted to separate files later)

// --- useSessions inline ---
interface Session {
  id: string;
  name: string;
  last_message: string;
  time: string;
  unread: number;
  message_count?: number;
  is_active?: boolean;
}

function useSessionsData(email: string | null, authFetch: (url: string, options?: RequestInit) => Promise<Response>) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    if (!email) return;
    try {
      const resp = await authFetch(`/api/sessions/${encodeURIComponent(email)}`);
      if (resp.ok) {
        const data = await resp.json();
        const list: Session[] = (data.sessions || []).map((s: Record<string, unknown>) => ({
          id: (s.session_id as string) || (s.id as string),
          name: ((s.preview as string) || '新对话').slice(0, 20),
          last_message: ((s.preview as string) || '').slice(0, 30),
          time: (s.last_message_time || s.last_active) ? fmtTime(((s.last_message_time as number) || (s.last_active as number))) : '',
          unread: 0,
          message_count: (s.message_count as number) || 0,
          is_active: (s.is_current as boolean) || false,
        }));
        setSessions(list);
        const cur = list.find(s => s.is_active);
        if (cur) setActiveSessionId(cur.id);
      }
    } catch { /* authFetch handles 401 */ }
  }, [email, authFetch]);

  const switchSession = useCallback(async (sid: string) => {
    if (!email) return;
    try {
      const resp = await authFetch('/api/sessions/switch?session_id=' + encodeURIComponent(sid), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      if (resp.ok) setActiveSessionId(sid);
    } catch { /* handled */ }
  }, [email, authFetch]);

  const createSession = useCallback(async () => {
    if (!email) return null;
    try {
      const resp = await authFetch('/api/sessions/new', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      if (resp.ok) {
        const data = await resp.json();
        return data.session_id as string;
      }
    } catch { /* handled */ }
    return null;
  }, [email, authFetch]);

  useEffect(() => { if (email) loadSessions(); }, [email, loadSessions]);

  return { sessions, activeSessionId, setActiveSessionId, loadSessions, switchSession, createSession };
}

function fmtTime(ts: number): string {
  const now = Date.now() / 1000;
  const diff = now - ts;
  if (diff < 60) return '刚刚';
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
  if (diff < 172800) return '昨天';
  return new Date(ts * 1000).toLocaleDateString('zh-CN');
}

// --- useChat inline ---
function useChatData(
  email: string | null,
  sessionId: string | null,
  authHeaders: () => Record<string, string>,
  handleAuthError: () => void,
) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Refs so callbacks don't need these as deps (avoids unnecessary effect re-fires)
  const authHeadersRef = useRef(authHeaders);
  authHeadersRef.current = authHeaders;
  const handleAuthErrorRef = useRef(handleAuthError);
  handleAuthErrorRef.current = handleAuthError;

  const loadConversation = useCallback(async (sid: string) => {
    if (!email) return;
    try {
      const resp = await fetch(
        `/api/conversations/${encodeURIComponent(email)}/${encodeURIComponent(sid)}`,
        { headers: { ...authHeadersRef.current() } },
      );
      if (resp.status === 401) { handleAuthErrorRef.current(); return; }
      if (resp.ok) {
        const data = await resp.json();
        const processedMessages: Message[] = [];
        (data.messages || []).forEach((m: Record<string, unknown>, i: number) => {
          const msg: Message = {
            id: m.id != null ? String(m.id) : `msg_${i}`,
            role: m.role as 'user' | 'assistant',
            content: typeof m.content === 'string' ? m.content : (m.content == null ? '' : String(m.content)),
            timestamp: (m.created_at as number) ?? (m.timestamp as number) ?? 0,
            status: (m.metadata as Record<string, unknown>)?.status as Message['status'],
            reply_to: (m.metadata as Record<string, unknown>)?.reply_to as string,
            thinking_time: (m.metadata as Record<string, unknown>)?.thinking_time as number,
            attachments: (m.attachments as Message['attachments']) ?? ((m.metadata as Record<string, unknown>)?.attachments as Array<Record<string, unknown>>)?.map((a: Record<string, unknown>) => ({
              id: (a.file_id as string) ?? (a.id as string) ?? '',
              filename: (a.filename as string) ?? '',
              url: (a.url as string) ?? '',
              type: (a.content_type as string) ?? (a.type as string) ?? '',
              size: (a.size as number) ?? undefined,
            })),
            metadata: (m.metadata as Record<string, unknown>) ?? {},
          };

          // If this is an assistant message with reasoning in metadata, create separate reasoning message
          if (msg.role === 'assistant' && msg.metadata && (msg.metadata.reasoning as string)) {
            const reasoning = msg.metadata.reasoning as string;
            processedMessages.push({
              id: `${msg.id}_reasoning`,
              role: 'assistant',
              content: reasoning,
              isReasoning: true,
              status: 'completed',
              timestamp: msg.timestamp,
            });
            // Remove reasoning from metadata in the reply message
            const { reasoning: _, ...restMetadata } = msg.metadata;
            msg.metadata = restMetadata;
          }

          processedMessages.push(msg);
        });
        setMessages(processedMessages);
      }
    } catch { /* connection monitor handles */ }
  }, [email]);

  const sendMessage = useCallback(async (text: string, attachments?: File[]) => {
    if (!email || !sessionId) return;
    if (!text.trim() && !attachments?.length) return;
    const now = Date.now();
    const userMsgId = `msg_${now}`;
    // 用于追踪当前活跃的工具卡片 ID（tool_call → tool_result 配对）
    let activeToolId: string | null = null;

    // Create local preview URLs for immediate thumbnail display
    const blobUrls = attachments?.map(f => URL.createObjectURL(f)) ?? [];
    const localAttachments = blobUrls.map((url, i) => ({
      id: `local_${i}`,
      filename: attachments![i].name,
      url,
      type: attachments![i].type,
      size: attachments![i].size,
    }));

    const userMsg: Message = {
      id: userMsgId, role: 'user', content: text, timestamp: now / 1000, status: 'pending',
      ...(localAttachments.length ? { attachments: localAttachments } : {}),
    };
    // Create two separate messages: reasoning and reply
    const reasoningId = `think_${now + 1}`;
    const replyId = `reply_${now + 1}`;
    const reasoningMsg: Message = { id: reasoningId, role: 'assistant', content: '', timestamp: now / 1000, status: 'processing', isReasoning: true };
    const replyMsg: Message = { id: replyId, role: 'assistant', content: '', timestamp: now / 1000, status: 'processing', reply_to: text.length > 20 ? text.slice(0, 20) + '...' : text };

    setMessages(prev => [...prev, userMsg, reasoningMsg, replyMsg]);
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      // Upload attachments, replacing blob URLs with real URLs as each upload completes
      let attachData: Record<string, unknown>[] = [];
      if (attachments?.length) {
        for (const [idx, f] of attachments.entries()) {
          const fd = new FormData(); fd.append('file', f);
          const r = await fetch('/api/upload', { method: 'POST', headers: authHeaders(), body: fd });
          if (r.status === 401) { handleAuthError(); return; }
          if (r.ok) {
            const d = await r.json();
            attachData.push({ file_id: d.file_id, filename: f.name, url: d.url, content_type: f.type, size: f.size });
            const blobUrl = blobUrls[idx];
            URL.revokeObjectURL(blobUrl);
            setMessages(prev => prev.map(m => m.id === userMsgId ? {
              ...m,
              attachments: m.attachments?.map(att => att.url === blobUrl ? { ...att, id: d.file_id, url: d.url } : att),
            } : m));
          }
        }
      }

      const settings = loadSettings();
      const body: Record<string, unknown> = { 
        email, 
        message: text, 
        session_id: sessionId,
        settings: {
          reasoning_level: settings.reasoningEffort,
          model: settings.model,
        },
      };
      if (attachData.length) body.attachments = attachData;

      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (resp.status === 401) { handleAuthError(); return; }
      // Mark user message as sent once request goes through
      setMessages(prev => prev.map(m => m.id === userMsgId ? { ...m, status: 'completed' } : m));
      if (!resp.ok) {
        setMessages(prev => prev.map(m => (m.id === reasoningId || m.id === replyId) ? { ...m, status: 'failed' } : m));
        setIsStreaming(false); return;
      }

      const reader = resp.body?.getReader();
      if (!reader) { setIsStreaming(false); return; }

      const decoder = new TextDecoder();
      let buffer = '';
      let currentEvent = '';
      let thinkingStart = 0;
      let fullContent = '';
      // 当前活跃的推理卡片 ID（工具调用后会创建新的推理卡片）
      let activeReasoningId = reasoningId;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event:')) { currentEvent = line.slice(6).trim(); }
          else if (line.startsWith('data:')) {
            const ds = line.slice(5).trim();
            if (currentEvent === 'thinking') { thinkingStart = Date.now(); }
            else if (currentEvent === 'reasoning') {
              try {
                const p = JSON.parse(ds);
                const chunk = typeof p.content === 'string' ? p.content : ds;
                if (chunk) setMessages(prev => prev.map(m =>
                  m.id === activeReasoningId ? { ...m, content: ((m.content as string) || '') + chunk } : m
                ));
              } catch {
                if (ds) setMessages(prev => prev.map(m =>
                  m.id === activeReasoningId ? { ...m, content: ((m.content as string) || '') + ds } : m
                ));
              }
            }
            // 处理工具调用开始事件：完成当前推理卡片，创建工具卡片
            else if (currentEvent === 'tool_call') {
              try {
                const p = JSON.parse(ds);
                const toolId = `tool_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
                activeToolId = toolId;
                const toolMsg: Message = {
                  id: toolId,
                  role: 'assistant',
                  content: '',
                  timestamp: Date.now() / 1000,
                  status: 'processing',
                  isTool: true,
                  toolName: p.name as string,
                  toolArgs: (p.args as Record<string, unknown>) ?? {},
                };
                // 完成当前推理卡片，在 replyMsg 前插入工具卡片
                setMessages(prev => {
                  const updated = prev.map(m =>
                    m.id === activeReasoningId ? { ...m, status: 'completed' as const } : m
                  );
                  // 在 replyMsg 前插入工具卡片
                  const replyIdx = updated.findIndex(m => m.id === replyId);
                  if (replyIdx >= 0) {
                    return [...updated.slice(0, replyIdx), toolMsg, ...updated.slice(replyIdx)];
                  }
                  return [...updated, toolMsg];
                });
              } catch { /* 解析失败忽略 */ }
            }
            // 处理工具调用结果事件：更新工具卡片，创建新推理卡片
            else if (currentEvent === 'tool_result') {
              try {
                const p = JSON.parse(ds);
                const elapsed = typeof p.elapsed_ms === 'number' ? p.elapsed_ms : undefined;
                const resultContent = typeof p.content === 'string' ? p.content : JSON.stringify(p.content);
                // 更新工具卡片内容和状态
                if (activeToolId) {
                  const tid = activeToolId;
                  setMessages(prev => prev.map(m =>
                    m.id === tid ? { ...m, status: 'completed' as const, content: resultContent, toolElapsed: elapsed } : m
                  ));
                  activeToolId = null;
                }
                // 为后续推理创建新的推理卡片，插入在 replyMsg 前
                const newReasoningId = `think_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
                activeReasoningId = newReasoningId;
                const newReasoningMsg: Message = {
                  id: newReasoningId,
                  role: 'assistant',
                  content: '',
                  timestamp: Date.now() / 1000,
                  status: 'processing',
                  isReasoning: true,
                };
                setMessages(prev => {
                  const replyIdx = prev.findIndex(m => m.id === replyId);
                  if (replyIdx >= 0) {
                    return [...prev.slice(0, replyIdx), newReasoningMsg, ...prev.slice(replyIdx)];
                  }
                  return [...prev, newReasoningMsg];
                });
              } catch { /* 解析失败忽略 */ }
            }
            else if (currentEvent === 'error') {
              try {
                const p = JSON.parse(ds);
                setMessages(prev => prev.map(m =>
                  (m.id === activeReasoningId || m.id === replyId) ? { ...m, status: 'failed', metadata: { ...m.metadata, error: p.message } } : m
                ));
              } catch { /* ignore */ }
            }
            else if (currentEvent === 'done') {
              const td = thinkingStart ? (Date.now() - thinkingStart) / 1000 : undefined;
              setMessages(prev => prev.map(m =>
                m.id === activeReasoningId ? { ...m, status: 'completed' } :
                m.id === replyId ? { ...m, status: 'completed', thinking_time: td, content: fullContent || m.content } : m
              ));
            }
            else if (ds === '[DONE]') { /* end */ }
            else {
              try {
                const p = JSON.parse(ds);
                const tok = p.choices?.[0]?.delta?.content || p.token || '';
                if (tok) { fullContent += tok; setMessages(prev => prev.map(m => m.id === replyId ? { ...m, content: fullContent } : m)); }
              } catch {
                if (ds && ds !== '[DONE]') { fullContent += ds; setMessages(prev => prev.map(m => m.id === replyId ? { ...m, content: fullContent } : m)); }
              }
            }
          }
          else if (line === '') {
            currentEvent = '';
          }
        }
      }

      setMessages(prev => prev.map(m => (m.id === activeReasoningId || m.id === replyId) && m.status === 'processing' ? { ...m, status: 'completed', content: m.id === replyId ? fullContent : m.content } : m));
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        setMessages(prev => prev.map(m => (m.id === reasoningId || m.id === replyId) ? { ...m, status: 'cancelled' } : m));
      } else {
        setMessages(prev => prev.map(m => (m.id === reasoningId || m.id === replyId) ? { ...m, status: 'failed' } : m));
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [email, sessionId, authHeaders, handleAuthError]);

  const stopStreaming = useCallback(() => { abortRef.current?.abort(); }, []);

  return { messages, isStreaming, sendMessage, stopStreaming, loadConversation, setMessages };
}

export default function ChatScreen({ email, authHeaders, authFetch, handleAuthError, onLogout }: ChatScreenProps) {
  const { sessions, activeSessionId, setActiveSessionId, loadSessions, switchSession, createSession } = useSessionsData(email, authFetch);
  const { messages, isStreaming, sendMessage, stopStreaming, loadConversation } = useChatData(email, activeSessionId, authHeaders, handleAuthError);

  const [focusTrigger, setFocusTrigger] = useState(0);
  const [toast, setToast] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [showPromptEditor, setShowPromptEditor] = useState(false);
  const [showContextPreview, setShowContextPreview] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [sessionsOpen, setSessionsOpen] = useState(false);
  const [settings, setSettings] = useState<ConveySettings>(loadSettings);
  const [keyboardPad, setKeyboardPad] = useState(0);
  const [connected, setConnected] = useState(true);
  const { isMobile } = useMobile();

  const creatingRef = useRef(false);
  const sessionsRef = useRef(sessions);
  useEffect(() => { sessionsRef.current = sessions; }, [sessions]);
  const handleCreateSessionRef = useRef<(() => Promise<void>) | null>(null);

  useEffect(() => {
    if (!isMobile) return;
    const vp = window.visualViewport;
    if (!vp) return;
    const onResize = () => {
      const offset = window.innerHeight - vp.height - vp.offsetTop;
      setKeyboardPad(offset > 0 ? offset : 0);
    };
    vp.addEventListener('resize', onResize);
    vp.addEventListener('scroll', onResize);
    return () => {
      vp.removeEventListener('resize', onResize);
      vp.removeEventListener('scroll', onResize);
    };
  }, [isMobile]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2500);
    return () => clearTimeout(t);
  }, [toast]);

  const quickReplies: QuickReply[] = useMemo(() => messages.length === 0 ? [
    { id: '1', label: '你好', content: '你好！' },
    { id: '2', label: '帮我分析', content: '请帮我分析一下这个问题' },
    { id: '3', label: '写代码', content: '请帮我写一段代码' },
    { id: '4', label: '总结', content: '请帮我总结一下' },
  ] : [
    { id: '1', label: '继续', content: '请继续' },
    { id: '2', label: '换个思路', content: '请换个思路回答' },
    { id: '3', label: '详细解释', content: '请详细解释一下' },
    { id: '4', label: '总结一下', content: '请总结一下上面的内容' },
  ], [messages.length]);

  // Load conversation when active session changes
  useEffect(() => {
    if (activeSessionId) {
      loadConversation(activeSessionId);
    }
  }, [activeSessionId, loadConversation]);

  const handleSelectSession = async (id: string) => {
    if (id === activeSessionId) return;
    await switchSession(id);
  };

  const handleCreateSession = async () => {
    const newId = await createSession();
    if (newId) {
      await switchSession(newId);
      await loadSessions();
      setFocusTrigger(t => t + 1);
    }
  };
  handleCreateSessionRef.current = handleCreateSession;

  const handleSend = useCallback(async (text: string, attachments?: File[]) => {
    await sendMessage(text, attachments);
    loadSessions();
  }, [sendMessage, loadSessions]);

  const handleQuickReply = (content: string) => {
    handleSend(content);
  };

  const handleSettings = () => {
    setSettingsOpen(true);
  };

  const handleDeleteSession = useCallback(async (sid: string) => {
    const isLastSession = sessionsRef.current.length <= 1;
    try {
      await authFetch(`/api/sessions/${encodeURIComponent(email)}/${encodeURIComponent(sid)}`, { method: 'DELETE' });
    } catch { /* handled */ }
    await loadSessions();
    if (isLastSession && !creatingRef.current) {
      creatingRef.current = true;
      try {
        await handleCreateSessionRef.current?.();
      } finally {
        creatingRef.current = false;
      }
    }
  }, [email, authFetch, loadSessions]);

  // Health check: ping /api/health every 30s
  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const resp = await fetch('/api/health', { headers: { ...authHeaders() } });
        if (!cancelled) setConnected(resp.ok);
      } catch {
        if (!cancelled) setConnected(false);
      }
    };
    check();
    const id = setInterval(check, 30000);
    return () => { cancelled = true; clearInterval(id); };
  }, [authHeaders]);

  // Suppress unused warning — setActiveSessionId used by session management
  void setActiveSessionId;

  return (
    <div className="chat-screen" style={keyboardPad > 0 ? { paddingBottom: keyboardPad } : undefined}>
      <TopBar
        email={email}
        onOpenSettings={handleSettings}
        onOpenSessions={() => setSessionsOpen(true)}
        onOpenPromptEditor={() => setShowPromptEditor(true)}
        onOpenContextPreview={() => setShowContextPreview(true)}
        onOpenAbout={() => setAboutOpen(true)}
        onLogout={onLogout}
        connected={connected}
      />
      <MessageList
        messages={messages}
        showReasoning={settings.showReasoning}
        showTools={settings.showToolCalls}
      />
      <InputBar onSend={handleSend} onStop={stopStreaming} isStreaming={isStreaming} focusTrigger={focusTrigger} />
      {toast && (
        <div className="toast-notify">{toast}</div>
      )}
      <SettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        settings={settings}
        onSettingsChange={setSettings}
      />
      <SystemPromptEditor
        open={showPromptEditor}
        onClose={() => setShowPromptEditor(false)}
        email={email}
        authHeaders={authHeaders}
      />
      <ContextPreview
        open={showContextPreview}
        onClose={() => setShowContextPreview(false)}
        email={email}
        sessionId={activeSessionId || ''}
        currentMessage={''}
        authHeaders={authHeaders}
        handleAuthError={handleAuthError}
      />
      <SessionPanel
        open={sessionsOpen}
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelect={async (id) => { await handleSelectSession(id); setSessionsOpen(false); }}
        onCreate={async () => { await handleCreateSession(); setSessionsOpen(false); }}
        onDelete={handleDeleteSession}
        onClose={() => setSessionsOpen(false)}
      />
      <AboutPanel
        open={aboutOpen}
        onClose={() => setAboutOpen(false)}
      />
    </div>
  );
}
