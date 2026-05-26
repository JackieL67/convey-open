import '@/styles/global.css';
import '@/styles/components.css';
import { useState, useCallback } from 'react';
import LoginScreen from '@/components/LoginScreen';
import ChatScreen from '@/components/ChatScreen';

const TOKEN_KEY = 'convey_token';
const USER_KEY = 'convey_user';

function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [userEmail, setUserEmail] = useState<string | null>(() => {
    const stored = localStorage.getItem(USER_KEY);
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        return parsed.email || null;
      } catch { return null; }
    }
    return null;
  });

  const isAuthenticated = !!token && !!userEmail;

  const authHeaders = useCallback((): Record<string, string> => {
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, [token]);

  const handleAuthError = useCallback(() => {
    setToken(null);
    setUserEmail(null);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }, []);

  const authFetch = useCallback(async (url: string, options: RequestInit = {}) => {
    const headers = {
      ...authHeaders(),
      ...options.headers,
    };
    const resp = await fetch(url, { ...options, headers });
    if (resp.status === 401) {
      handleAuthError();
      throw new Error('UNAUTHORIZED');
    }
    return resp;
  }, [authHeaders, handleAuthError]);

  const handleLogin = useCallback(async (email: string, inviteCode?: string) => {
    // Generate device_id (UUID fallback for non-HTTPS)
    const deviceId = (typeof crypto !== 'undefined' && crypto.randomUUID)
      ? crypto.randomUUID()
      : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
          const r = Math.random() * 16 | 0;
          return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
        });

    const body: Record<string, string> = { email, device_id: deviceId };
    if (inviteCode) body.invite_code = inviteCode;

    try {
      const resp = await fetch('/api/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const data = await resp.json();

      if (resp.status === 403 && data.need_invite) {
        return { needInvite: true, remaining: data.remaining };
      }

      if (!resp.ok) {
        return { error: data.detail || '登录失败' };
      }

      setToken(data.token);
      setUserEmail(data.email);
      localStorage.setItem(TOKEN_KEY, data.token);
      localStorage.setItem(USER_KEY, JSON.stringify({ email: data.email }));

      return { success: true };
    } catch (err: unknown) {
      return { error: err instanceof Error ? err.message : '网络错误' };
    }
  }, []);

  const handleLogout = useCallback(() => {
    setToken(null);
    setUserEmail(null);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }, []);

  if (!isAuthenticated) {
    return <LoginScreen onLogin={handleLogin} />;
  }

  return (
    <ChatScreen
      email={userEmail!}
      authHeaders={authHeaders}
      authFetch={authFetch}
      handleAuthError={handleAuthError}
      onLogout={handleLogout}
    />
  );
}

export default App;
