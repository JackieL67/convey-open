import { useState } from 'react';
import type { User } from '@/types';

interface LoginScreenProps {
  onLogin: (email: string, inviteCode?: string) => Promise<{ success?: boolean; needInvite?: boolean; error?: string }>;
}

export default function LoginScreen({ onLogin }: LoginScreenProps) {
  const [email, setEmail] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needInvite, setNeedInvite] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const result = await onLogin(email.trim(), inviteCode.trim() || undefined);

      if (result.needInvite) {
        setNeedInvite(true);
        setError('需要邀请码才能注册');
      } else if (result.error) {
        setError(result.error);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-screen">
      <div className="logo">🤝</div>
      <h1>
        Con<span className="brand-accent">vey</span>
      </h1>
      <p className="subtitle">AI 平权，从这里开始</p>

      <form className="login-form" onSubmit={handleSubmit}>
        <input
          type="email"
          placeholder="请输入邮箱"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={loading}
          autoFocus
        />

        {needInvite && (
          <input
            className="invite-input"
            type="text"
            placeholder="请输入邀请码"
            value={inviteCode}
            onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
            disabled={loading}
          />
        )}

        {error && <div className="error-msg">{error}</div>}

        <button type="submit" disabled={loading || !email.trim()}>
          {loading ? '登录中...' : needInvite ? '注册' : '开始使用'}
        </button>
      </form>
    </div>
  );
}
