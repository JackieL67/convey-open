import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import type { Message } from '@/types';

interface MessageListProps {
  messages: Message[];
  showReasoning?: boolean;
  showTools?: boolean;
}

interface ParsedAtt {
  name: string;
  url: string;
  isImage: boolean;
}

function parseAttachmentText(text: string): { cleanText: string; atts: ParsedAtt[] } {
  const atts: ParsedAtt[] = [];
  const cleanText = text.replace(
    /\[用户上传了(图片|文件): ([^,\]]+), URL: ([^\]]+)\]/g,
    (_, type: string, name: string, url: string) => {
      atts.push({ name: name.trim(), url: url.trim(), isImage: type === '图片' });
      return '';
    }
  );
  return { cleanText: cleanText.trim(), atts };
}

function processInline(text: string, kp: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /(\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\))/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let idx = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) nodes.push(text.slice(lastIndex, match.index));
    if (match[0].startsWith('**')) {
      nodes.push(<strong key={`${kp}-b${idx}`}>{match[2]}</strong>);
    } else if (match[0].startsWith('`')) {
      nodes.push(<code key={`${kp}-c${idx}`} className="md-ci">{match[3]}</code>);
    } else {
      nodes.push(
        <a key={`${kp}-a${idx}`} className="md-link" href={match[5]} target="_blank" rel="noreferrer">
          {match[4]}
        </a>
      );
    }
    lastIndex = match.index + match[0].length;
    idx++;
  }
  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return nodes;
}

function renderMarkdown(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const parts = text.split(/(```[\s\S]*?```)/g);

  parts.forEach((part, i) => {
    if (i % 2 === 1) {
      const m = part.match(/```\w*\n?([\s\S]*?)```/);
      const code = m ? m[1] : part.slice(3, -3);
      nodes.push(
        <pre key={`cb${i}`} className="md-block">
          <code>{code}</code>
        </pre>
      );
    } else {
      part.split('\n').forEach((line, j) => {
        const kp = `${i}-${j}`;
        if (/^[-*] /.test(line)) {
          nodes.push(
            <span key={kp} className="md-li">
              {'• '}{processInline(line.slice(2), kp)}
            </span>
          );
        } else if (/^\d+\. /.test(line)) {
          const pfx = line.match(/^(\d+\. )/)?.[1] ?? '';
          nodes.push(
            <span key={kp} className="md-li">
              {pfx}{processInline(line.slice(pfx.length), kp)}
            </span>
          );
        } else if (line === '') {
          nodes.push(<br key={kp} />);
        } else {
          nodes.push(
            <span key={kp} style={{ display: 'block' }}>
              {processInline(line, kp)}
            </span>
          );
        }
      });
    }
  });

  return nodes;
}

// 根据工具名称返回对应的图标
function getToolIcon(toolName: string): string {
  const name = toolName.toLowerCase();
  if (name.includes('search') || name.includes('web')) return '🔍';
  if (name.includes('image') || name.includes('vision') || name.includes('screenshot')) return '🖼️';
  if (name.includes('file') || name.includes('read') || name.includes('write')) return '📄';
  if (name.includes('code') || name.includes('exec') || name.includes('run')) return '⚙️';
  if (name.includes('browser') || name.includes('url') || name.includes('http')) return '🌐';
  if (name.includes('calc') || name.includes('math')) return '🧮';
  return '🔧';
}

// 格式化工具参数摘要（最多显示 60 个字符）
function fmtToolArgs(args: Record<string, unknown> | undefined): string {
  if (!args) return '';
  const pairs = Object.entries(args)
    .map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(', ');
  return pairs.length > 80 ? pairs.slice(0, 77) + '...' : pairs;
}

// 工具卡片组件
function ToolCard({ message }: { message: Message }) {
  const icon = getToolIcon(message.toolName ?? '');
  const isProcessing = message.status === 'processing';
  const argsSummary = fmtToolArgs(message.toolArgs);
  const elapsedSec = message.toolElapsed != null
    ? message.toolElapsed >= 1000
      ? `${(message.toolElapsed / 1000).toFixed(1)}s`
      : `${message.toolElapsed}ms`
    : null;

  return (
    <div className="message-wrapper assistant tool-message">
      <div className="tool-card">
        <div className="tool-card-header">
          <span className="tool-icon">{icon}</span>
          <span className="tool-name">{message.toolName ?? '工具调用'}</span>
          {isProcessing && <span className="tool-status-processing thinking-pulse">●</span>}
          {!isProcessing && elapsedSec && (
            <span className="tool-elapsed">{elapsedSec}</span>
          )}
        </div>
        {argsSummary && (
          <div className="tool-args">{argsSummary}</div>
        )}
        {!isProcessing && message.content && (
          <details className="tool-result-details">
            <summary className="tool-result-summary">查看结果</summary>
            <div className="tool-result-content">{message.content}</div>
          </details>
        )}
      </div>
    </div>
  );
}

export default function MessageList({ messages, showReasoning = true, showTools = true }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const formatMsgTime = (timestamp: number | undefined): string => {
    if (!timestamp) return '';
    const d = new Date(timestamp * 1000);
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
  };

  return (
    <div className="message-list scrollbar-hide">
      {messages.map((msg) => {
        // 工具卡片不显示时跳过
        if (msg.isTool && !showTools) {
          return null;
        }

        // Skip rendering reasoning messages if showReasoning is false
        if (msg.isReasoning && !showReasoning) {
          return null;
        }

        const isUser = msg.role === 'user';
        const content = typeof msg.content === 'string' ? msg.content : '';
        const { cleanText, atts: parsedAtts } = isUser
          ? parseAttachmentText(content)
          : { cleanText: content, atts: [] };
        // Prefer structured attachments on the message object (set during send with blob/server URLs)
        const atts = isUser && msg.attachments?.length
          ? msg.attachments.map(a => ({ name: a.filename ?? '', url: a.url ?? '', isImage: a.type?.startsWith('image/') ?? false }))
          : parsedAtts;

        // 工具卡片渲染
        if (msg.isTool) {
          return <ToolCard key={msg.id} message={msg} />;
        }

        // Reasoning message rendering
        if (msg.isReasoning) {
          return (
            <div key={msg.id} className="message-wrapper assistant reasoning-message">
              <div className="message-bubble reasoning-bubble">
                <div className="reasoning-header">🤔 推理过程</div>
                <div className="reasoning-content">
                  {content.replace(/^\n+/, '')}
                </div>
              </div>
            </div>
          );
        }

        return (
          <div key={msg.id} className={`message-wrapper ${isUser ? 'user' : 'assistant'}`}>
            {/* Streaming AI message with no content yet: only show status dot */}
            {!isUser && !content ? (
              <div className="message-meta">
                {msg.status === 'completed' && <span style={{ color: 'var(--success)' }}>●</span>}
                {msg.status === 'cancelled' && <span style={{ color: 'var(--warm-text-light)' }}>⊘</span>}
              </div>
            ) : (
              <div className="message-bubble">
                {/* Attachments */}
                {atts.length > 0 && (
                  <div className="att-list">
                    {atts.map((att, idx) =>
                      att.isImage ? (
                        <a key={idx} className="att-image" href={att.url} target="_blank" rel="noreferrer">
                          <img src={att.url} alt={att.name} />
                          <span className="att-name">{att.name}</span>
                        </a>
                      ) : (
                        <a key={idx} className="att-file" href={att.url} target="_blank" rel="noreferrer">
                          <span>📄</span>
                          <span className="att-name">{att.name}</span>
                        </a>
                      )
                    )}
                  </div>
                )}

                {/* Message content */}
                {isUser ? (
                  <span style={{ whiteSpace: 'pre-wrap' }}>
                    {cleanText || (msg.status === 'processing' ? '思考中...' : '')}
                  </span>
                ) : (
                  <div className="md-content">
                    {content ? renderMarkdown(content.replace(/^\n+/, '')) : null}
                  </div>
                )}
              </div>
            )}

            {/* Time + status */}
            <div className="message-meta">
              <span>{formatMsgTime(msg.timestamp)}</span>
              {isUser && msg.status === 'completed' && <span>完成</span>}
              {msg.status === 'pending' && <span>待处理</span>}
              {msg.status === 'cancelled' && <span style={{ color: 'var(--warm-text-light)' }}>已取消</span>}
              {msg.status === 'failed' && <span style={{ color: 'var(--error)' }}>发送失败</span>}
              {!isUser && msg.status === 'processing' && <span className="thinking-pulse" style={{ color: 'var(--accent)' }}>●</span>}
              {!isUser && msg.status === 'completed' && <span style={{ color: 'var(--success)' }}>●</span>}
              {!isUser && msg.status === 'cancelled' && <span style={{ color: 'var(--warm-text-light)' }}>⊘</span>}
            </div>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
