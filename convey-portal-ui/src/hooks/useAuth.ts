import { useState, useEffect, useCallback } from 'react';
import type { User } from '@/types';

const TOKEN_KEY = 'convey_token';
const USER_KEY = 'convey_user';

export function useAuth() {
  const [user, setUser] = useState<User | null>(() => {
    const stored = localStorage.getItem(USER_KEY);
    return stored ? JSON.parse(stored) : null;
  });
  const [token, setToken] = useState<string | null>(() => {
    return localStorage.getItem(TOKEN_KEY);
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Persist to localStorage
  useEffect(() => {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  }, [token]);

  useEffect(() => {
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(USER_KEY);
    }
  }, [user]);

  const authHeaders = useCallback((): Record<string, string> => {
    if (!token) return {};
    return { Authorization: `Bearer ${token}` };
  }, [token]);

  // Authenticated fetch with 401 handling
  const authFetch = useCallback(async (url: string, options: RequestInit = {}) => {
    const headers = {
      ...authHeaders(),
      'Content-Type': 'application/json',
      ...options.headers,
    };

    const resp = await fetch(url, { ...options, headers });

    if (resp.status === 401) {
      handleAuthError();
      throw new Error('UNAUTHORIZED');
    }

    return resp;
  }, [authHeaders]);

  const handleAuthError = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setError('登录已过期，请重新登录');
  }, []);

  const login = useCallback(async (email: string, inviteCode?: string) => {
    setLoading(true);
    setError(null);
    try {
      const body: Record<string, string> = { email };
      if (inviteCode) body.invite_code = inviteCode;

      const resp = await fetch('/api/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const data = await resp.json();

      if (resp.status === 403 && data.need_invite) {
        setError('需要邀请码');
        return { needInvite: true, remaining: data.remaining };
      }

      if (!resp.ok) {
        setError(data.detail || '登录失败');
        return { error: data.detail };
      }

      setToken(data.token);
      setUser({
        email: data.email,
        session_id: data.session_id,
        display_name: data.display_name || '',
      });

      return { success: true };
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '网络错误';
      setError(msg);
      return { error: msg };
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }, []);

  return {
    user,
    token,
    loading,
    error,
    isAuthenticated: !!token && !!user,
    authHeaders,
    authFetch,
    login,
    logout,
    handleAuthError,
  };
}
