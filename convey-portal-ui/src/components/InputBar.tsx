import { useState, useRef, useEffect } from 'react';

interface InputBarProps {
  onSend: (text: string, attachments?: File[]) => void;
  onStop: () => void;
  isStreaming: boolean;
  focusTrigger?: number;
}

export default function InputBar({ onSend, onStop, isStreaming, focusTrigger }: InputBarProps) {
  const [inputValue, setInputValue] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, [inputValue]);

  useEffect(() => {
    if (focusTrigger) textareaRef.current?.focus();
  }, [focusTrigger]);

  const handleSend = () => {
    const text = inputValue.trim();
    if (!text && pendingFiles.length === 0) return;
    onSend(text, pendingFiles.length > 0 ? pendingFiles : undefined);
    setInputValue('');
    setPendingFiles([]);
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (isStreaming) return;
      handleSend();
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    setPendingFiles(prev => [...prev, ...files]);
    // Reset input so same file can be selected again
    e.target.value = '';
  };

  const removeFile = (index: number) => {
    setPendingFiles(prev => prev.filter((_, i) => i !== index));
  };

  const canSend = inputValue.trim().length > 0 || pendingFiles.length > 0;

  return (
    <div className="input-bar">
      {/* Pending file tags */}
      {pendingFiles.length > 0 && (
        <div style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap', padding: '0 4px' }}>
          {pendingFiles.map((f, i) => (
            <span
              key={i}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 4,
                padding: '4px 8px', borderRadius: 8,
                background: 'var(--warm-bg)', border: '1px solid var(--warm-border)',
                fontSize: 12, color: 'var(--warm-text)',
              }}
            >
              📎 {f.name.slice(0, 15)}
              <button
                onClick={() => removeFile(i)}
                style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--error)', fontSize: 14, padding: 0, lineHeight: 1 }}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="input-row">
        {/* Attach button */}
        <button className="attach-btn" onClick={() => fileInputRef.current?.click()} title="附件">
          <span className="icon-paperclip" />
        </button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          style={{ display: 'none' }}
          onChange={handleFileSelect}
        />

        {/* Text input */}
        <textarea
          ref={textareaRef}
          className="chat-input"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="说点什么吧..."
          rows={1}
        />

        {/* Stop button — always visible, grey when idle, red when streaming */}
        <button
          className={`stop-btn${isStreaming ? ' enabled' : ''}`}
          onClick={onStop}
          disabled={!isStreaming}
          title="停止"
        >
          <span className="icon-stop" />
          <span>停止</span>
        </button>

        {/* Send button */}
        <button
          className={`send-btn${canSend ? ' enabled' : ''}`}
          onClick={handleSend}
          disabled={!canSend || isStreaming}
          title="发送"
        >
          <span className="icon-send" />
          <span>发送</span>
        </button>
      </div>
    </div>
  );
}
