interface AboutPanelProps {
  open: boolean;
  onClose: () => void;
}

const VERSION = "1.0.0";
const RELEASE_DATE = "2026-05-26";

const FEATURES = [
  {
    title: "🤖 智能对话",
    items: ["DeepSeek V4 驱动，支持流式输出", "Thinking 推理过程可视化", "Flash / Pro 双模型切换"],
  },
  {
    title: "🔧 工具系统",
    items: ["网页搜索 — 实时信息检索", "文件读取 — 支持 PDF、Markdown、代码文件", "图片识别 — AI 视觉能力描述图像"],
  },
  {
    title: "📎 文件管理",
    items: ["拖拽上传图片与文档", "附件全量预览", "公开链接免登录访问"],
  },
  {
    title: "🧠 记忆与上下文",
    items: ["跨会话长期记忆", "自定义系统提示词与回复规范", "上下文压缩，长对话不丢失"],
  },
  {
    title: "🔒 私有部署",
    items: ["自托管，数据完全可控", "邀请码注册体系", "Nginx 反向代理 + systemd 管理"],
  },
];

export default function AboutPanel({ open, onClose }: AboutPanelProps) {
  return (
    <>
      {open && <div className="settings-overlay" onClick={onClose} />}
      <div className={`settings-panel about-panel${open ? ' open' : ''}`}>
        <div className="settings-header">
          <span className="settings-title">关于 Convey</span>
          <button className="settings-close" onClick={onClose}>✕</button>
        </div>

        <div className="settings-body">
          <div className="about-hero">
            <div className="about-logo">Con<span className="brand-accent">vey</span></div>
            <div className="about-version">v{VERSION} · {RELEASE_DATE}</div>
            <p className="about-tagline">
              你的智能文件助手 — 上传、提问、获得洞察
            </p>
          </div>

          {FEATURES.map((section) => (
            <div key={section.title} className="about-section">
              <h3 className="about-section-title">{section.title}</h3>
              <ul className="about-feature-list">
                {section.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ))}

          <div className="about-footer">
            <p>Built with ❤️ using React + Python + DeepSeek</p>
            <p>© 2026 Convey. All rights reserved.</p>
          </div>
        </div>
      </div>
    </>
  );
}
