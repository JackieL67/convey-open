import type { QuickReply } from '@/types';

interface QuickReplyStripProps {
  replies?: QuickReply[];
  onSelect: (content: string) => void;
}

const defaultReplies: QuickReply[] = [
  { id: '1', label: '你好', content: '你好！' },
  { id: '2', label: '帮我分析', content: '请帮我分析一下这个问题' },
  { id: '3', label: '写代码', content: '请帮我写一段代码' },
  { id: '4', label: '总结', content: '请帮我总结一下' },
];

export default function QuickReplyStrip({ replies = defaultReplies, onSelect }: QuickReplyStripProps) {
  return (
    <div className="quick-reply-strip">
      <div className="strip-label">快捷回复</div>
      <div className="strip-scroll scrollbar-hide">
        {replies.map((reply) => (
          <button
            key={reply.id}
            className="quick-reply-card"
            onClick={() => onSelect(reply.content)}
          >
            <span className="qr-label">{reply.label}</span>
            <span className="qr-preview">{reply.content}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
