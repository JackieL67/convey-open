import { useState, useEffect, useCallback, useRef } from 'react';
import type { Session } from '@/types';

export function useSessions(email: string | null, authFetch: (url: string, options?: RequestInit) => Promise<Response>) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const refreshRef = useRef<() => void>(() => {});

  const loadSessions = useCallback(async () => {
    if (!email) return;
    setLoading(true);
    try {
      const resp = await authFetch(`/api/sessions/${encodeURIComponent(email)}`);
      if (resp.ok) {
        const data = await resp.json();
        const sessionList: Session[] = (data.sessions || []).map((s: Record<string, unknown>) => ({
          id: s.session_id as string || s.id as string,
          name: (s.preview as string || '新对话').slice(0, 20),
          last_message: (s.preview as string || '').slice(0, 30),
          time: s.last_active ? formatTime(s.last_active as number) : '',
          unread: 0,
          message_count: s.message_count as number || 0,
          is_active: s.is_current as boolean || false,
        }));
        setSessions(sessionList);
        const current = sessionList.find(s => s.is_active);
        if (current) setActiveSessionId(current.id);
      }
    } catch {
      // Will be handled by authFetch 401 check
    } finally {
      setLoading(false);
    }
  }, [email, authFetch]);

  const switchSession = useCallback(async (sessionId: string) => {
    if (!email) return;
    try {
      const resp = await authFetch('/api/sessions/switch?session_id=' + encodeURIComponent(sessionId), {
        method: 'POST',
      });
      if (resp.ok) {
        setActiveSessionId(sessionId);
      }
    } catch {
      // handled by authFetch
    }
  }, [email, authFetch]);

  const createSession = useCallback(async () => {
    if (!email) return;
    try {
      const resp = await authFetch('/api/sessions/new', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setActiveSessionId(data.session_id);
        await loadSessions();
        return data.session_id;
      }
    } catch {
      // handled
    }
    return null;
  }, [email, authFetch, loadSessions]);

  const deleteSession = useCallback(async (sessionId: string) => {
    if (!email) return;
    try {
      const resp = await authFetch(`/api/sessions/${encodeURIComponent(sessionId)}`, {
        method: 'DELETE',
      });
      if (resp.ok) {
        await loadSessions();
      }
    } catch {
      // handled
    }
  }, [email, authFetch, loadSessions]);

  // Load sessions on mount and when email changes
  useEffect(() => {
    if (email) loadSessions();
  }, [email, loadSessions]);

  refreshRef.current = loadSessions;

  return {
    sessions,
    activeSessionId,
    setActiveSessionId,
    loading,
    loadSessions,
    switchSession,
    createSession,
    deleteSession,
  };
}

function formatTime(timestamp: number): string {
  const now = Date.now() / 1000;
  const diff = now - timestamp;
  if (diff < 86400) {
    const d = new Date(timestamp * 1000);
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
  }
  if (diff < 172800) return '昨天';
  if (diff < 604800) {
    const days = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    return days[new Date(timestamp * 1000).getDay()];
  }
  return new Date(timestamp * 1000).toLocaleDateString('zh-CN');
}
