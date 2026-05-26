import { useEffect, useRef, useState } from 'react';

interface TopBarProps {
  email: string;
  onOpenSettings: () => void;
  onOpenSessions: () => void;
  onOpenPromptEditor: () => void;
  onOpenContextPreview: () => void;
  onOpenAbout: () => void;
  onLogout: () => void;
  connected?: boolean;
}

export default function TopBar({ email, onOpenSettings, onOpenSessions, onOpenPromptEditor, onOpenContextPreview, onOpenAbout, onLogout, connected = true }: TopBarProps) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const initial = email ? email.charAt(0).toUpperCase() : '?';

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      const target = e.target as Element;
      if (target.closest('.dropdown-item')) return;
      if (menuRef.current && !menuRef.current.contains(target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  return (
    <div className="top-bar">
      <div className="brand">
        Con<span className="brand-accent">vey</span>
        <span className={`health-dot ${connected ? 'connected' : 'disconnected'}`} title={connected ? '已连接' : '连接断开'} />
      </div>

      <div className="top-bar-more" ref={menuRef}>
        <button className="more-btn" onClick={() => setOpen(o => !o)}>
          <span className="more-icon">⋯</span>
          <span>更多</span>
        </button>

        {open && (
          <div className="more-dropdown">
            <div className="dropdown-account">
              <div className="avatar">{initial}</div>
              <span className="account-email">{email}</span>
            </div>
            <div className="dropdown-divider" />
            <button
              className="dropdown-item"
              onClick={() => { onOpenSettings(); setOpen(false); }}
            >
              <span>⚙</span>
              <span>设置</span>
            </button>
            <button
              className="dropdown-item"
              onClick={() => { onOpenPromptEditor(); setOpen(false); }}
            >
              <span>💬</span>
              <span>系统提示词</span>
            </button>
            <button
              className="dropdown-item"
              onClick={() => { onOpenContextPreview(); setOpen(false); }}
            >
              <span>🔍</span>
              <span>Prompt 上下文</span>
            </button>
            <button
              className="dropdown-item"
              onClick={() => { onOpenSessions(); setOpen(false); }}
            >
              <span>🗂</span>
              <span>对话</span>
            </button>
            <button
              className="dropdown-item"
              onClick={() => { onOpenAbout(); setOpen(false); }}
            >
              <span>ℹ</span>
              <span>关于</span>
            </button>
            <button
              className="dropdown-item logout"
              onClick={() => { onLogout(); setOpen(false); }}
            >
              <span>↪</span>
              <span>退出登录</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
