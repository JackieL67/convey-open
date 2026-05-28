# DeepSeek Chat

> 基于 DeepSeek V4 的开源自托管 AI 对话平台 | Self-hosted AI Chat Platform Powered by DeepSeek V4

DeepSeek Chat 是一个开源的 AI 对话平台，基于 DeepSeek V4 模型。支持流式对话、思维链推理、21 个内置工具、任务规划引擎和安全代码沙箱。一键部署，数据完全私有。

DeepSeek Chat is an open-source AI chat platform powered by DeepSeek V4. It features streaming conversation, chain-of-thought reasoning, 21 built-in tools, a task planning engine, and a secure code sandbox. One-command deploy, your data stays private.

---

## 功能亮点 / Highlights

### 智能对话 / Intelligent Conversation

- **流式推理可视化** — DeepSeek V4 Thinking 模式，实时展示 AI 思考过程
- **双模型切换** — V4 Flash (快速) 与 V4 Pro (深度推理) 一键切换
- **上下文压缩** — 长对话自动压缩，不会丢失上下文
- **多会话管理** — 同时维护多个独立对话，无缝切换

### 21 工具系统 / 21-Tool System

**8 个内置工具：**

| 工具 | 说明 |
|------|------|
| web_search | 实时网络搜索 (Tavily) |
| read_file | 文件读取 (PDF/MD/TXT/代码) |
| describe_image | 图片识别 (Claude Sonnet Vision) |
| get_weather | 天气查询 |
| get_time | 时间/时区查询 |
| get_trends | 微博/知乎热搜 |
| search_bilibili | B站内容搜索 |
| execute_python | Python 代码沙箱执行 |

**13 个 MCP 工具：** Tavily 搜索套件 (5) + Sequential Thinking + Puppeteer 浏览器自动化 (7)

- **Tool Router** — 语义路由引擎，21 工具自动匹配用户意图，精准选择
- **Tool Loop** — 多轮工具循环，支持复杂工作流 (搜索→读取→分析→再搜索)

### Agent 能力 / Agent Capabilities

- **Planner 任务规划** — LLM 驱动，将复杂目标拆解为可执行步骤，逐步推进
- **Sandbox 代码沙箱** — 安全的 Python 执行环境，支持数据分析和图表生成
- **MCP Gateway** — 标准化工具接入，兼容 MCP 协议的第三方工具即插即用
- **File System** — 统一文件管理，上传/输出/缓存一体化

### 部署 / Deployment

- **一键部署** — systemd + Nginx，开箱即用
- **双实例架构** — 稳定版 + 调试版隔离运行，互不影响
- **邀请码注册** — HMAC-SHA256 Token 认证，安全可控

---

## 架构 / Architecture

```
┌─────────────────────────────────────────────────┐
│         React SPA (TypeScript + Vite)             │
│      SSE streaming · Tool Cards · Settings        │
└────────────────────┬────────────────────────────┘
                     │ /api/*
┌────────────────────▼────────────────────────────┐
│          FastAPI Server (Python)                  │
│   Auth · Chat · Upload · Session · Context        │
└────────────────────┬────────────────────────────┘
                     │ RPC
┌────────────────────▼────────────────────────────┐
│        Conversation Engine (Python)               │
│  ChatHandler · Tool Loop · Tool Router · Planner  │
└───┬────────┬──────────┬───────────┬─────────────┘
    │        │          │           │
┌───▼──┐ ┌───▼────┐ ┌───▼────┐ ┌───▼──────────┐
│Bridge│ │  Tool  │ │ Memory │ │  File System  │
│DS V4 │ │  8+13  │ │ Honcho │ │   Manager     │
└──────┘ └────────┘ └────────┘ └───────────────┘
```

**分层说明：**
- **Portal 层** — React SPA，SSE 流式渲染，支持工具卡片、设置面板、暗色模式
- **Engine 层** — ChatHandler 编排对话流程，Tool Loop 管理多轮工具调用，Tool Router 做语义路由
- **Service 层** — Bridge (LLM 协议适配)、Tool Executor (并发执行)、Memory (跨会话记忆)、File System (文件管理)
- **Data 层** — SQLite 持久化，DeepSeek API 直连，Tavily 搜索

---

## 快速开始 / Getting Started

### 前置条件 / Prerequisites

- Python 3.10+
- Node.js 18+ (仅前端开发)
- DeepSeek API Key
- Tavily API Key (搜索)
- ZenMux API Key (图片识别)

### 环境变量 / Environment

| 变量 | 必需 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | ✅ | DeepSeek V4 API 密钥 |
| `TAVILY_API_KEY` | ✅ | Tavily 搜索 API |
| `ZENMUX_API_KEY` | ✅ | ZenMux API (图片识别) |
| `CONVEY_TOKEN_SECRET` | - | Token 签名密钥，自动生成 |
| `CONVEY_PORT` | - | 端口，默认 3000 |

### 安装运行 / Install & Run

```bash
# 1. 克隆
git clone https://github.com/JackieL67/deepseek-chat.git
cd deepseek-chat

# 2. 构建前端
cd convey-portal-ui
pnpm install && pnpm build
cd ..

# 3. 配置环境
cp .env.example .env
# 编辑 .env 填入 API keys

# 4. 启动
source .env
python3 user-portal/server.py

# 或使用 systemd 部署 (推荐)
sudo cp deploy/convey-portal.service /etc/systemd/system/
sudo systemctl enable --now convey-portal
```

访问 `http://localhost:3000`

### Nginx 反代 (可选) / Nginx Reverse Proxy (Optional)

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_buffering off;           # SSE 必须
        proxy_read_timeout 300s;
        client_max_body_size 50M;      # 文件上传
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## API 概览 / API Overview

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/auth` | POST | 注册/登录 (返回 Token) |
| `/api/chat` | POST | SSE 流式对话 (含工具调用) |
| `/api/upload` | POST | 文件上传 |
| `/api/files/{file_id}` | GET | 文件下载 (公开访问) |
| `/api/tools` | GET | 工具列表与状态 |
| `/api/sessions/new` | POST | 创建新会话 |
| `/api/context-preview` | POST | 上下文预览 |
| `/api/settings/{email}/system-prompt` | GET/PUT | 系统提示词管理 |

启动后访问 `/docs` 查看完整 Swagger 文档。

---

## 技术栈 / Tech Stack

| 模块 | 技术 |
|------|------|
| Frontend | React 18 + TypeScript + Vite |
| Backend | FastAPI + Uvicorn (async) |
| Database | SQLite (aiosqlite) |
| Auth | HMAC-SHA256 Token |
| AI Model | DeepSeek V4 (原生 API，流式 + reasoning) |
| Vision | Claude Sonnet (via zenmux) |
| Search | Tavily API |
| Memory | Honcho (pgvector + Redis) |
| Embedding | text-embedding-3-small (1536-d) |
| Deployment | systemd + Nginx |

---

## 路线图 / Roadmap

- **🔍 工具扩展** — 更多内置工具，降低对社区 MCP 的依赖
- **⚡ 性能优化** — 流式响应延迟优化，长上下文压缩增强
- **📱 PWA 支持** — 移动端渐进式 Web 应用
- **🔌 插件系统** — 第三方工具接入标准接口
- **🌐 多语言** — 国际化支持

---

## 许可证 / License

[MIT](LICENSE)
