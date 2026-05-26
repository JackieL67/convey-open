import { useState, useEffect } from 'react';

interface SystemPromptEditorProps {
  open: boolean;
  onClose: () => void;
  email: string;
  authHeaders: () => Record<string, string>;
  onSuccess?: () => void;
}

export default function SystemPromptEditor({
  open,
  onClose,
  email,
  authHeaders,
  onSuccess,
}: SystemPromptEditorProps) {
  const [prompt, setPrompt] = useState('');
  const [promptSaved, setPromptSaved] = useState(false);
  const [promptError, setPromptError] = useState('');

  const [replyRules, setReplyRules] = useState('');
  const [rulesError, setRulesError] = useState('');
  const [rulesSaved, setRulesSaved] = useState(false);

  const [loading, setLoading] = useState(false);
  const [showComingSoon, setShowComingSoon] = useState(false);

  useEffect(() => {
    if (!open) return;
    const loadBoth = async () => {
      try {
        setLoading(true);
        setPromptError('');
        setRulesError('');

        const [promptResp, rulesResp] = await Promise.all([
          fetch(`/api/settings/${encodeURIComponent(email)}/system-prompt`, { headers: authHeaders() }),
          fetch(`/api/settings/${encodeURIComponent(email)}/reply-rules`, { headers: authHeaders() }),
        ]);

        if (promptResp.ok) {
          const data = await promptResp.json();
          setPrompt(data.system_prompt || '你是一个技术助手。');
          setPromptSaved(false);
        } else {
          setPromptError('加载系统提示词失败');
        }

        if (rulesResp.ok) {
          const data = await rulesResp.json();
          setReplyRules(data.reply_rules || '## 回复规范\n- 用 Markdown 格式回复\n- 代码块标注使用的编程语言\n- 不确定时直接说明，不要编造\n- 用中文回复');
          setRulesSaved(false);
        } else {
          setRulesError('加载回复规范失败');
        }
      } catch {
        setPromptError('网络错误，请重试');
        setRulesError('网络错误，请重试');
      } finally {
        setLoading(false);
      }
    };
    loadBoth();
  }, [open, email, authHeaders]);

  const handleSavePrompt = async () => {
    try {
      setLoading(true);
      setPromptError('');
      const resp = await fetch(`/api/settings/${encodeURIComponent(email)}/system-prompt`, {
        method: 'PUT',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ system_prompt: prompt }),
      });
      if (resp.ok) {
        setPromptSaved(true);
        if (onSuccess) onSuccess();
        setTimeout(() => setPromptSaved(false), 2000);
      } else {
        setPromptError('保存失败，请重试');
      }
    } catch {
      setPromptError('网络错误，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveRules = async () => {
    try {
      setLoading(true);
      setRulesError('');
      const resp = await fetch(`/api/settings/${encodeURIComponent(email)}/reply-rules`, {
        method: 'PUT',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ reply_rules: replyRules }),
      });
      if (resp.ok) {
        setRulesSaved(true);
        if (onSuccess) onSuccess();
        setTimeout(() => setRulesSaved(false), 2000);
      } else {
        setRulesError('保存失败，请重试');
      }
    } catch {
      setRulesError('网络错误，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleResetRules = async () => {
    try {
      setLoading(true);
      setRulesError('');
      const resp = await fetch(`/api/settings/${encodeURIComponent(email)}/reply-rules/reset`, {
        method: 'POST',
        headers: authHeaders(),
      });
      if (resp.ok) {
        const data = await resp.json();
        setReplyRules(data.reply_rules);
        setRulesSaved(true);
        if (onSuccess) onSuccess();
        setTimeout(() => setRulesSaved(false), 2000);
      } else {
        setRulesError('恢复失败，请重试');
      }
    } catch {
      setRulesError('网络错误，请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {open && <div className="settings-overlay" onClick={onClose} />}
      <div className={`settings-panel${open ? ' open' : ''}`}>
        <div className="settings-header">
          <span className="settings-title">编辑提示词</span>
          <button className="settings-close" onClick={onClose}>✕</button>
        </div>

        <div className="settings-body" style={{ gap: 20, overflowY: 'auto', flex: 1 }}>

          {/* 第一段：用户自定义提示词 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <label style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
              你的提示词
              <span style={{ display: 'block', fontSize: 12, fontWeight: 400, color: 'var(--warm-text)', marginTop: 2 }}>
                自定义 AI 助手的角色和行为
              </span>
            </label>
            <textarea
              className="sp-textarea"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="例如：你是一个技术助手，专门帮助用户解决编程问题。"
              disabled={loading}
              style={{ minHeight: 160 }}
            />
            {promptError && <div className="sp-error">{promptError}</div>}
            {promptSaved && <div className="sp-success">✅ 已保存</div>}
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="sp-save-btn" onClick={handleSavePrompt} disabled={loading || prompt.trim() === ''} style={{ flex: 1 }}>
                {loading ? '保存中...' : '保存提示词'}
              </button>
              <button className="sp-guide-btn" onClick={() => setShowComingSoon(true)} disabled={loading}>
                引导生成
              </button>
            </div>
            {showComingSoon && (
              <div className="sp-coming-soon">
                🚧 功能待上线 — 未来将通过问答和用例帮你找到最适合的提示词
                <button className="sp-dismiss-btn" onClick={() => setShowComingSoon(false)}>知道了</button>
              </div>
            )}
          </div>

          <hr style={{ border: 'none', borderTop: '1px solid var(--warm-border)', margin: '4px 0' }} />

          {/* 第二段：回复规范 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <label style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
              回复规范
              <span style={{ display: 'block', fontSize: 12, fontWeight: 400, color: 'var(--warm-text)', marginTop: 2 }}>
                AI 回复的格式与风格指引
              </span>
            </label>
            <div className="sp-rules-warning">
              ⚠ 修改可能影响 AI 回复质量，请谨慎操作
            </div>
            <textarea
              className="sp-textarea sp-rules-textarea"
              value={replyRules}
              onChange={(e) => setReplyRules(e.target.value)}
              placeholder="## 回复规范"
              disabled={loading}
              style={{ minHeight: 120 }}
            />
            {rulesError && <div className="sp-error">{rulesError}</div>}
            {rulesSaved && <div className="sp-success">✅ 已保存</div>}
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="sp-save-btn" onClick={handleSaveRules} disabled={loading || replyRules.trim() === ''} style={{ flex: 1 }}>
                {loading ? '保存中...' : '保存规范'}
              </button>
              <button className="sp-reset-btn" onClick={handleResetRules} disabled={loading}>
                恢复默认
              </button>
            </div>
          </div>

          <div className="sp-rules-footer">
          </div>
          </div>
        </div>

      <style>{`
        .sp-textarea {
          width: 100%;
          padding: 12px;
          border: 1px solid var(--warm-border);
          border-radius: var(--radius-md);
          background: var(--warm-surface);
          color: var(--text-primary);
          font-family: 'Monaco', 'Courier New', monospace;
          font-size: 13px;
          line-height: 1.5;
          resize: vertical;
          box-sizing: border-box;
          transition: border-color 0.2s, box-shadow 0.2s;
        }
        .sp-textarea:focus {
          outline: none;
          border-color: var(--accent);
          box-shadow: 0 0 0 3px var(--accent-alpha);
        }
        .sp-textarea:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
        .sp-textarea::placeholder {
          color: var(--warm-text-light);
        }
        .sp-rules-textarea {
          border-color: rgba(231, 76, 60, 0.3);
          background: var(--accent-light);
        }
        .sp-rules-textarea:focus {
          border-color: var(--error);
          box-shadow: 0 0 0 3px rgba(231, 76, 60, 0.15);
        }
        .sp-error {
          padding: 8px 12px;
          background: rgba(231, 76, 60, 0.08);
          border: 1px solid rgba(231, 76, 60, 0.2);
          border-radius: 6px;
          color: var(--error);
          font-size: 12px;
        }
        .sp-success {
          padding: 8px 12px;
          background: rgba(100, 200, 120, 0.1);
          border: 1px solid rgba(100, 200, 120, 0.25);
          border-radius: 6px;
          color: var(--success);
          font-size: 12px;
        }
        .sp-rules-warning {
          padding: 8px 12px;
          background: rgba(255, 159, 67, 0.1);
          border: 1px solid rgba(255, 159, 67, 0.25);
          border-radius: 6px;
          color: var(--accent-hover);
          font-size: 12px;
          line-height: 1.4;
        }
        .sp-save-btn, .sp-reset-btn, .sp-close-btn {
          padding: 10px 16px;
          border-radius: var(--radius-md);
          border: none;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.15s;
        }
        .sp-save-btn {
          background: var(--accent);
          color: #fff;
        }
        .sp-save-btn:hover:not(:disabled) {
          background: var(--accent-hover);
        }
        .sp-save-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .sp-reset-btn {
          background: var(--warm-bg);
          color: var(--warm-text);
          border: 1px solid var(--warm-border);
        }
        .sp-reset-btn:hover:not(:disabled) {
          background: var(--warm-hover);
          color: var(--text-primary);
        }
        .sp-reset-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .sp-close-btn {
          width: 100%;
          background: var(--warm-bg);
          color: var(--warm-text);
          border: 1px solid var(--warm-border);
          margin-top: 8px;
        }
        .sp-close-btn:hover {
          background: var(--warm-hover);
          color: var(--text-primary);
        }
        .sp-guide-btn {
          padding: 10px 16px;
          border-radius: var(--radius-md);
          border: 1px dashed var(--accent);
          background: var(--accent-light);
          color: var(--accent-hover);
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.15s;
          white-space: nowrap;
        }
        .sp-guide-btn:hover:not(:disabled) {
          background: rgba(255, 159, 67, 0.15);
          border-style: solid;
        }
        .sp-guide-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .sp-coming-soon {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
          padding: 10px 12px;
          background: var(--accent-light);
          border: 1px solid rgba(255, 159, 67, 0.25);
          border-radius: 6px;
          color: var(--accent-hover);
          font-size: 12px;
          line-height: 1.4;
        }
        .sp-dismiss-btn {
          background: none;
          border: 1px solid rgba(255, 159, 67, 0.3);
          border-radius: 4px;
          color: var(--accent-hover);
          font-size: 11px;
          padding: 4px 10px;
          cursor: pointer;
          white-space: nowrap;
          flex-shrink: 0;
        }
        .sp-dismiss-btn:hover {
          background: rgba(255, 159, 67, 0.1);
        }
      `}</style>
    </>
  );
}
