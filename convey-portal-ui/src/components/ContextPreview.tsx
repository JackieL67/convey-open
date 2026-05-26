import { useState, useEffect } from 'react';
import type { Message } from '@/types';

interface ContextPreviewData {
  system_prompt: string;
  user_memory: string;
  dynamic_context: string;
  history: Array<{
    role: 'user' | 'assistant';
    content: string;
    full_length: number;
  }>;
  current_message: string;
  history_count: number;
  history_token_estimate: number;
  system_token_estimate: number;
  user_memory_token_estimate: number;
  dynamic_context_token_estimate: number;
  current_token_estimate: number;
  total_token_estimate: number;
  attachments_count: number;
  attachments: Array<{ filename: string; file_id: string }>;
  active_tools: string[];
  tools_count: number;
}

interface ContextPreviewProps {
  open: boolean;
  onClose: () => void;
  email: string;
  sessionId: string;
  currentMessage: string;
  authHeaders: () => Record<string, string>;
  handleAuthError: () => void;
}

export default function ContextPreview({
  open,
  onClose,
  email,
  sessionId,
  currentMessage,
  authHeaders,
  handleAuthError,
}: ContextPreviewProps) {
  const [data, setData] = useState<ContextPreviewData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    system: true,
    memory: true,
    dynamic: false,
    history: false,
    current: true,
    attachments: false,
    tools: false,
  });

  useEffect(() => {
    if (!open || !sessionId) return;

    const fetchPreview = async () => {
      setLoading(true);
      setError('');
      try {
        const resp = await fetch('/api/context-preview', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...authHeaders(),
          },
          body: JSON.stringify({
            email,
            session_id: sessionId,
            message: currentMessage,
          }),
        });

        if (resp.status === 401) {
          handleAuthError();
          return;
        }

        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          throw new Error(errData.detail || `错误 ${resp.status}`);
        }

        const preview = await resp.json();
        setData(preview);
      } catch (err) {
        setError(err instanceof Error ? err.message : '加载上下文失败');
      } finally {
        setLoading(false);
      }
    };

    fetchPreview();
  }, [open, sessionId, currentMessage, email, authHeaders, handleAuthError]);

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  return (
    <>
      {open && <div className="settings-overlay" onClick={onClose} />}
      <div className={`settings-panel context-preview${open ? ' open' : ''}`}>
        <div className="settings-header">
          <span className="settings-title">Prompt 上下文</span>
          <button className="settings-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="settings-body">
          {/* 总览信息 */}
          <div className="context-overview">
            <div className="overview-item">
              <span className="overview-label">总 Token 估算</span>
              <span className="overview-value">{loading ? '...' : (data?.total_token_estimate ?? '-')}</span>
            </div>
            <div className="overview-item">
              <span className="overview-label">历史消息</span>
              <span className="overview-value">{loading ? '...' : (data?.history_count ?? '-')}</span>
            </div>
            <div className="overview-item">
              <span className="overview-label">📎 会话附件</span>
              <span className="overview-value">{loading ? '...' : `${data?.attachments_count ?? 0} 个`}</span>
            </div>
            <div className="overview-item">
              <span className="overview-label">🔧 活跃工具</span>
              <span className="overview-value">{loading ? '...' : `${data?.tools_count ?? 0} 个`}</span>
            </div>
          </div>

          {loading && (
            <div className="context-loading">
              <span>加载中...</span>
            </div>
          )}

          {error && (
            <div className="context-error">
              <span>⚠ {error}</span>
            </div>
          )}

          {data && (
            <>
              {/* 系统提示词 */}
              <div className="context-section">
                <div
                  className="context-section-header"
                  onClick={() => toggleSection('system')}
                >
                  <span className="section-icon">
                    {expandedSections.system ? '▼' : '▶'}
                  </span>
                  <span className="section-title">
                    系统提示词 (System Prompt)
                  </span>
                  <span className="section-meta">
                    {data.system_token_estimate} tokens
                  </span>
                </div>
                {expandedSections.system && (
                  <pre className="context-content">
                    {data.system_prompt || '（无）'}
                  </pre>
                )}
              </div>

              {/* 用户记忆 */}
              <div className="context-section">
                <div
                  className="context-section-header"
                  onClick={() => toggleSection('memory')}
                >
                  <span className="section-icon">
                    {expandedSections.memory ? '▼' : '▶'}
                  </span>
                  <span className="section-title">用户记忆 (Memory)</span>
                  <span className="section-meta">
                    {data.user_memory_token_estimate} tokens
                  </span>
                </div>
                {expandedSections.memory && (
                  <pre className="context-content">
                    {data.user_memory || '暂无记忆'}
                  </pre>
                )}
              </div>

              {/* 动态上下文 */}
              <div className="context-section">
                <div
                  className="context-section-header"
                  onClick={() => toggleSection('dynamic')}
                >
                  <span className="section-icon">
                    {expandedSections.dynamic ? '▼' : '▶'}
                  </span>
                  <span className="section-title">
                    动态上下文 (Dynamic Context)
                  </span>
                  <span className="section-meta">
                    {data.dynamic_context_token_estimate} tokens
                  </span>
                </div>
                {expandedSections.dynamic && (
                  <pre className="context-content">
                    {data.dynamic_context || '（无）'}
                  </pre>
                )}
              </div>

              {/* 历史消息 */}
              <div className="context-section">
                <div
                  className="context-section-header"
                  onClick={() => toggleSection('history')}
                >
                  <span className="section-icon">
                    {expandedSections.history ? '▼' : '▶'}
                  </span>
                  <span className="section-title">历史消息 (History)</span>
                  <span className="section-meta">
                    {data.history_count} 条，约 {data.history_token_estimate}{' '}
                    tokens
                  </span>
                </div>
                {expandedSections.history && (
                  <div className="context-history">
                    {data.history.length === 0 ? (
                      <div className="context-empty">无历史消息</div>
                    ) : (
                      data.history.map((msg, idx) => (
                        <div key={idx} className="history-item">
                          <span className={`history-role ${msg.role}`}>
                            {msg.role === 'user' ? '👤 User' : '🤖 AI'}
                          </span>
                          <div className="history-content">
                            <code>{msg.content}</code>
                            {msg.full_length > 200 && (
                              <span className="history-truncated">
                                {' '}
                                ...（共 {msg.full_length} 字符）
                              </span>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>

              {/* 当前消息 */}
              <div className="context-section">
                <div
                  className="context-section-header"
                  onClick={() => toggleSection('current')}
                >
                  <span className="section-icon">
                    {expandedSections.current ? '▼' : '▶'}
                  </span>
                  <span className="section-title">当前用户消息</span>
                  <span className="section-meta">
                    {data.current_token_estimate} tokens
                  </span>
                </div>
                {expandedSections.current && (
                  <pre className="context-content">
                    {data.current_message || '（空）'}
                  </pre>
                )}
              </div>

              {/* 附件状态 */}
              <div className="context-section">
                <div
                  className="context-section-header"
                  onClick={() => toggleSection('attachments')}
                >
                  <span className="section-icon">
                    {expandedSections.attachments ? '▼' : '▶'}
                  </span>
                  <span className="section-title">📎 会话附件</span>
                  <span className="section-meta">
                    {data.attachments_count} 个
                  </span>
                </div>
                {expandedSections.attachments && (
                  <div className="context-list-content">
                    {data.attachments.length === 0 ? (
                      <div className="context-empty">暂无附件</div>
                    ) : (
                      data.attachments.map((att, idx) => (
                        <div key={idx} className="context-list-item">
                          <span className="list-item-icon">📄</span>
                          <span className="list-item-text">{att.filename}</span>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>

              {/* 工具状态 */}
              <div className="context-section">
                <div
                  className="context-section-header"
                  onClick={() => toggleSection('tools')}
                >
                  <span className="section-icon">
                    {expandedSections.tools ? '▼' : '▶'}
                  </span>
                  <span className="section-title">🔧 活跃工具</span>
                  <span className="section-meta">
                    {data.tools_count} 个
                  </span>
                </div>
                {expandedSections.tools && (
                  <div className="context-list-content">
                    {data.active_tools.length === 0 ? (
                      <div className="context-empty">暂无活跃工具</div>
                    ) : (
                      data.active_tools.map((tool, idx) => (
                        <div key={idx} className="context-list-item">
                          <span className="list-item-icon">⚡</span>
                          <span className="list-item-text">{tool}</span>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
