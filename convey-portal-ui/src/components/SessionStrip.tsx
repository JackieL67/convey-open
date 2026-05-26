import type { Session } from '@/types';

interface SessionStripProps {
  sessions: Session[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onCreateSession: () => void;
}

export default function SessionStrip({ sessions, activeSessionId, onSelectSession, onCreateSession }: SessionStripProps) {
  return (
    <div className="session-strip">
      <div className="strip-label">当前会话</div>
      <div className="strip-scroll scrollbar-hide">
        {sessions.length === 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', width: 130, padding: '10px 12px', color: 'var(--warm-text)', fontSize: 12, gap: 4 }}>
            <span style={{ fontSize: 20 }}>💬</span>
            <span>暂无会话</span>
          </div>
        )}
        {sessions.map((session) => {
          const isActive = session.id === activeSessionId;
          return (
            <button
              key={session.id}
              className={`session-card${isActive ? ' active' : ''}`}
              onClick={() => onSelectSession(session.id)}
            >
              {session.unread > 0 && (
                <div className="unread-badge">{session.unread}</div>
              )}
              <span className="session-preview">
                {session.last_message || '新对话'}
              </span>
              {session.time && <span className="session-time">{session.time}</span>}
            </button>
          );
        })}

        {/* New session button */}
        <button className="session-card" onClick={onCreateSession} style={{ justifyContent: 'center', alignItems: 'center' }}>
          <span style={{ fontSize: 24, color: 'var(--warm-text)' }}>+</span>
          <span style={{ fontSize: 11, color: 'var(--warm-text)', marginTop: 4 }}>新对话</span>
        </button>
      </div>
    </div>
  );
}
