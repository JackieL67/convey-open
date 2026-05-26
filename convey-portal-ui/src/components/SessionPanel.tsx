interface Session {
  id: string;
  name: string;
  last_message: string;
  time: string;
  unread: number;
  message_count?: number;
  is_active?: boolean;
}

interface SessionPanelProps {
  open: boolean;
  sessions: Session[];
  activeSessionId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}

export default function SessionPanel({
  open,
  sessions,
  activeSessionId,
  onSelect,
  onCreate,
  onDelete,
  onClose,
}: SessionPanelProps) {
  return (
    <>
      {open && <div className="settings-overlay" onClick={onClose} />}
      <div className={`settings-panel session-panel${open ? ' open' : ''}`}>
        <div className="settings-header">
          <span className="settings-title">对话管理</span>
          <button className="settings-close" onClick={onClose}>✕</button>
        </div>

        <div className="session-panel-body">
          <div className="session-panel-new">
            <button className="session-new-btn" onClick={onCreate}>
              <span>＋</span>
              <span>新建对话</span>
            </button>
          </div>

          <div className="session-panel-list">
            {sessions.length === 0 && (
              <div className="session-panel-empty">暂无对话</div>
            )}
            {sessions.map(s => (
              <div
                key={s.id}
                className={`session-panel-item${s.id === activeSessionId ? ' active' : ''}`}
                onClick={() => onSelect(s.id)}
              >
                <div className="session-panel-item-body">
                  <div className="session-panel-preview">
                    {s.name || s.last_message || '新对话'}
                  </div>
                  {s.time && (
                    <div className="session-panel-time">{s.time}</div>
                  )}
                </div>
                <button
                  className="session-panel-del"
                  onClick={e => { e.stopPropagation(); onDelete(s.id); }}
                  title="删除"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="session-panel-footer">
          共 {sessions.length} 个对话
        </div>
      </div>
    </>
  );
}
