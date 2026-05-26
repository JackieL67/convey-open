# Convey

> 你的智能文件助手 — 上传、提问、获得洞察 | Your AI File Assistant — Upload, Ask, Get Insights

Convey 是一个自托管的 AI 对话平台。上传文件、提出问题，AI 理解内容并给出洞察。数据在你的服务器上，完全可控。

Convey is a self-hosted AI conversation platform. Upload files, ask questions, and the AI understands the content to deliver insights. Your data stays on your server, fully under your control.

---

## 愿景 / Vision

**中文：**

AI Agent 正在重塑软件交互方式，但当前主流方案存在结构性问题：云端 SaaS 模式下用户数据托管在第三方平台，开发者工具则对终端用户门槛过高。Convey 的愿景是建立 **用户自主拥有的 AI Agent**——Agent 作为私有资产部署，记忆作为私有数据存储，同时保持终端产品的易用性。

Agent 的核心价值不仅在于对话交互，更在于 **用户画像构建、项目上下文理解、工具授权调用与持续协作**。当这些能力依赖第三方平台时，用户对自身数据和 Agent 行为的控制权实质上被让渡。Convey 的设计原则是用户主权优先：Agent 的部署位置——本地、私有服务器或云沙箱——由用户自主决定，但所有权始终归属用户。

此外，Convey 采用 **记忆与 Agent 解耦** 的架构设计。当前已实现会话级记忆的跨设备共享——用户在不同终端登录同一账号，对话历史完整同步。下一阶段将实现用户记忆的跨 Agent 继承——当用户在不同专业 Agent 之间切换时，偏好、上下文与项目记忆自动继承，消除冷启动成本。

**English:**

AI Agents are reshaping software interaction, but current mainstream approaches have structural issues: cloud SaaS models host user data on third-party platforms, while developer-oriented tools present prohibitive barriers to end users. Convey's vision is to establish **user-owned AI Agents** — agents deployed as private assets, memory stored as private data, while maintaining the usability of a consumer product.

The core value of agents extends beyond conversational interaction to **user profile construction, project context understanding, authorized tool invocation, and continuous collaboration**. When these capabilities depend on third-party platforms, user control over their data and agent behavior is effectively ceded. Convey's design principle is user sovereignty first: the deployment location — local machine, private server, or cloud sandbox — is user-determined, but ownership always resides with the user.

Furthermore, Convey employs a **memory-agent decoupled** architecture. The current release supports cross-device session memory — users logging in from different terminals see fully synchronized conversation history. The next milestone is cross-agent user memory — when users switch between specialized agents, preferences, context, and project memory are automatically inherited, eliminating cold-start overhead.

---

## 当前状态 / Current Status

> **v1.0.0** — 核心功能完整，生产可用 / Core features complete, production-ready

### 对话与推理 / Conversation & Reasoning

| 能力 / Capability | 状态 / Status |
|---|---|
| 流式对话 (SSE) / Streaming chat | ✅ Done |
| Thinking 推理过程可视化 / Reasoning visualization | ✅ Done |
| Flash / Pro 双模型切换 / Dual model switching | ✅ Done |
| 多会话管理 / Multi-session management | ✅ Done |
| 自定义系统提示词与回复规范 / Custom system prompts & reply rules | ✅ Done |
| 上下文压缩，长对话不丢失 / Context compression for long conversations | ✅ Done |
| 跨会话长期记忆 / Cross-session memory | ✅ Done |

### 工具系统 / Tool System

| 能力 / Capability | 状态 / Status |
|---|---|
| 网页搜索 (Tavily) / Web search | ✅ Done |
| 文件读取 (PDF/MD/TXT/代码) / File reading | ✅ Done |
| 图片识别 (Claude Sonnet) / Image description | ✅ Done |
| 并发工具执行 / Concurrent tool execution | ✅ Done |
| 多轮工具循环 (Tool Loop) / Multi-round tool loop | ✅ Done |

### 文件管理 / File Management

| 能力 / Capability | 状态 / Status |
|---|---|
| 拖拽上传图片与文档 / Drag-and-drop file upload | ✅ Done |
| 附件全量预览 / Full attachment preview | ✅ Done |
| 公开链接免登录访问 / Public link access without login | ✅ Done |

### 部署与安全 / Deployment & Security

| 能力 / Capability | 状态 / Status |
|---|---|
| 用户认证 + 邀请码 / Auth + invite codes | ✅ Done |
| systemd + Nginx 部署 / systemd + Nginx deployment | ✅ Done |
| DeepSeek V4 直连 / Direct DeepSeek V4 integration | ✅ Done |

### 后续规划 / Roadmap

- **Planner** — 任务规划引擎，显式拆解复杂目标 / Task planning with explicit decomposition
- **Sandbox** — 安全代码执行，支持数据分析与图表生成 / Secure code execution for data analysis
- **MCP Gateway** — 标准化工具接入，社区工具即插即用 / Standardized tool gateway
- **多 Agent 支持** — 不同场景切换专业 Agent / Multi-agent with role specialization
- **团队协作** — 多人共享 Agent，协同项目 / Team collaboration

---

## 架构 / Architecture

```
┌─────────────────────────────────────────────────────┐
│              React Portal (TypeScript + Vite)         │
│                    SSE streaming                      │
└──────────────────────┬──────────────────────────────┘
                       │ /api/*
┌──────────────────────▼──────────────────────────────┐
│              User Portal (FastAPI)                    │
│     Auth · Chat API · File Upload · Session Mgmt     │
└──────────────────────┬──────────────────────────────┘
                       │ Python import (RPC mode)
┌──────────────────────▼──────────────────────────────┐
│                   Engine (Python)                     │
│  chat_handler (Tool Loop) · tool_executor · memory   │
└────┬─────────┬──────────┬─────────────┬─────────────┘
     │         │          │             │
┌────▼──┐ ┌───▼────┐ ┌───▼─────┐ ┌─────▼──────┐
│Bridge │ │  Tool  │ │ Memory  │ │    CRM     │
│(DS V4)│ │Executor│ │(Honcho) │ │  (SQLite)  │
└───┬───┘ └───┬────┘ └─────────┘ └────────────┘
    │         │
┌───▼───┐ ┌───▼────────────────────┐
│DeepSeek│ │  Tools                 │
│  V4    │ │  web_search / read_file│
└───────┘ │  / describe_image       │
          └────────────────────────┘
```

**中文说明：** Portal 是唯一的对外 Web 服务。Engine 通过 Python 模块直接调用（RPC 模式）。Bridge 层负责 DeepSeek V4 协议对接（流式 tool_calls + reasoning_content）。工具执行器并发调用，不阻塞对话流。

**English:** The Portal is the sole external-facing web service. Engine is invoked via Python module import (RPC mode). The Bridge layer handles DeepSeek V4 protocol (streaming tool_calls + reasoning_content). The tool executor runs concurrently, non-blocking the conversation flow.

---

## 技术栈 / Tech Stack

| 模块 / Module | 技术 / Technology | 说明 / Description |
|---|---|---|
| Frontend | React 18 + TypeScript + Vite | 响应式 SPA，SSE 流式渲染 / Responsive SPA with SSE streaming |
| Backend | FastAPI + Uvicorn | 异步 Web 服务 / Async web service |
| Database | SQLite (aiosqlite) | 轻量持久化 / Lightweight persistence |
| Auth | HMAC-SHA256 Token | 无状态认证 / Stateless authentication |
| AI Model | DeepSeek V4 (deepseek.py) | 原生 API 对接，流式 + reasoning / Native API integration |
| Vision | Claude Sonnet (via zenmux) | 图片识别 / Image description |
| Search | Tavily API | 实时搜索 / Real-time search |
| Memory | Honcho | 跨会话长期记忆 / Cross-session memory |
| CRM | SQLite | 邀请码管理 / Invite code management |

---

## 项目结构 / Project Structure

```
convey/
├── convey-portal-ui/     # React 前端 / React frontend
│   └── src/
│       ├── components/   # UI 组件 (ChatScreen, SettingsPanel, AboutPanel...)
│       ├── hooks/        # React hooks (auth, chat, sessions)
│       └── styles/       # CSS 样式 / CSS styles
├── user-portal/          # FastAPI 后端 / FastAPI backend
│   ├── server.py         # 主服务器 / Main server
│   ├── auth.py           # 认证模块 / Auth module
│   ├── engine_client.py  # Engine 客户端 / Engine client
│   └── static/           # 前端构建产物 / Frontend build output
├── engine/               # 对话引擎 / Conversation engine
│   ├── chat_handler.py   # 聊天处理 + Tool Loop
│   ├── engine.py         # 核心引擎（DI 装配）
│   ├── db.py             # 数据库层 / Database layer
│   └── config.py         # 配置管理 / Configuration
├── llm-bridge/           # LLM 桥接层 / LLM Bridge
│   ├── client.py         # DeepSeek SSE 流式客户端
│   ├── deepseek.py       # DeepSeek API 封装
│   ├── stream.py         # SSE 流解析器
│   └── messages.py       # 消息构建
├── util/tools/           # 工具系统 / Tool System
│   ├── web_search.py     # Tavily 搜索
│   ├── read_file.py      # 文件读取 (PyMuPDF)
│   ├── describe_image.py # 图片识别 (Claude)
│   ├── executor.py       # 并发工具执行器
│   └── registry.py       # 工具注册表
├── data/                 # 数据层 / Data layer
│   ├── context/          # 上下文管理器
│   └── memory_store/     # 记忆存储
├── memory/               # 记忆模块 / Memory
├── crm/                  # CRM 模块 / CRM module
└── start.sh              # 启动脚本 / Startup script
```

---

## 快速开始 / Getting Started

### 前置条件 / Prerequisites

- Python 3.10+
- Node.js 18+ (仅前端开发需要 / for frontend dev only)
- pnpm
- DeepSeek API Key

### 环境变量 / Environment Variables

| 变量 / Variable | 必需 / Required | 说明 / Description |
|---|---|---|
| `DEEPSEEK_API_KEY` | 是 / Yes | DeepSeek V4 API 密钥 |
| `TAVILY_API_KEY` | 是 / Yes | Tavily 搜索 API 密钥（工具系统） |
| `ZENMUX_API_KEY` | 是 / Yes | ZenMux API 密钥（图片识别） |
| `CONVEY_TOKEN_SECRET` | 否 / No | Token 签名密钥，自动生成 / Auto-generated |
| `CONVEY_PORT` | 否 / No | 服务端口，默认 3000 / Server port, default 3000 |

### 启动 / Start

```bash
# 1. 克隆 + 安装 / Clone + Install
git clone https://github.com/JackieL67/convey-open.git
cd convey-open

# 2. 配置环境变量 / Configure environment
cp .env.example .env
# 编辑 .env 填入 API keys

# 3. 构建前端 / Build frontend
cd convey-portal-ui
pnpm install
pnpm build
cd ..

# 4. 启动 / Start
source .env
python3 user-portal/server.py
```

访问 `http://localhost:3000` / Visit `http://localhost:3000`

### 前端开发 / Frontend Development

```bash
cd convey-portal-ui
pnpm install
pnpm dev      # 开发服务器 / Dev server on :5173
pnpm build    # 构建生产版本 / Build for production
```

---

## API 概览 / API Overview

| 端点 / Endpoint | 方法 / Method | 说明 / Description |
|---|---|---|
| `/api/health` | GET | 健康检查 / Health check |
| `/api/auth` | POST | 注册/登录（返回 token）/ Register/Login (returns token) |
| `/api/chat` | POST | SSE 流式对话（含工具调用） / SSE streaming chat with tool calls |
| `/api/upload` | POST | 文件上传 / File upload |
| `/api/files/{file_id}` | GET | 文件下载（支持公开访问） / File download (public access) |
| `/api/sessions/new` | POST | 创建新会话 / Create session |
| `/api/context-preview` | POST | 上下文预览（system prompt + 附件 + 工具） |
| `/api/settings/{email}/system-prompt` | GET/PUT | 系统提示词管理 |
| `/api/settings/{email}/reply-rules` | GET/PUT | 回复规范管理 |

完整 API 文档：启动服务后访问 `/docs` (Swagger UI)
Full API docs: visit `/docs` after starting the server (Swagger UI)

---

## 设计决策 / Design Decisions

### 为什么 Bridge 直连 DeepSeek 而不是通过框架？

Convey 深度依赖 DeepSeek V4 的 thinking mode（reasoning_content）和流式 tool_calls。直接封装 `deepseek.py` 可以完整控制协议细节——包括 reasoning_content 跨轮次回传、tool_call delta 合并、以及 finish_reason 精确判断。这些特性是通用 LLM 框架（LangChain/LiteLLM）难以完美适配的。

### 为什么用 SQLite 而不是 PostgreSQL？

Convey 设计为轻量级单机部署。SQLite 零配置、零运维，通过 WAL 模式支持并发读。对于自托管场景（单用户到数百用户），SQLite 完全够用且部署成本最低。

Convey is designed for lightweight single-machine deployment. SQLite requires zero configuration and zero ops, with concurrent reads via WAL mode. For self-hosted scenarios (single user to hundreds), SQLite is sufficient with the lowest deployment cost.

### 为什么用 HMAC Token 而不是 JWT？

HMAC-SHA256 token 是自包含的（包含 email + 过期时间 + 签名），无需数据库查询即可验证。相比 JWT，实现更简单，不需要额外依赖。

HMAC-SHA256 tokens are self-contained (email + expiry + signature), verifiable without database queries. Compared to JWT, the implementation is simpler with no extra dependencies.

### Tool Loop 设计：为什么 Bridge 层不调工具？

Tool Loop 的核心环路在 Engine（chat_handler），Bridge 只管 DeepSeek 协议。Bridge 通过增强 SSE done 事件报告 `finish_reason` 和 `tool_calls`，Engine 解析后执行工具、回填结果、再调 Bridge。这种分层让协议层保持纯净，工具扩展不影响 LLM 对接。

---

## 收获与反思 / What I Learned

**中文：**

1. **SSE 流式渲染的坑** — 前端必须正确处理 SSE 事件边界（空行分隔），否则会出现消息截断或重复渲染
2. **E2E 测试不能只靠 curl** — curl 每次拿新 token，不覆盖浏览器中过期 token 的场景。必须包含"过期 token"用例
3. **DeepSeek V4 thinking mode 的 protocol tax** — reasoning_content 必须在多轮 tool calling 中回传，否则 API 直接 400。这不是 bug 而是协议要求
4. **Tool Loop 的上下文保持** — 第二轮工具调用时如果用户消息从 messages 中消失，LLM 会失去对话上下文。解决方法是显式在 compressed history 中保留当前 user 消息
5. **轻量架构的选择** — SQLite + FastAPI + React 的组合，让一个全职开发者能在短时间内完成可用的全栈产品

**English:**

1. **SSE streaming gotchas** — Frontend must correctly handle SSE event boundaries (blank-line separators), otherwise messages truncate or render twice
2. **E2E tests need more than curl** — curl gets fresh tokens each time, missing the expired-token-in-browser scenario. Must include "expired token" test cases
3. **DeepSeek V4 thinking mode protocol tax** — reasoning_content must be passed back across multi-round tool calls, otherwise the API returns 400. This is a protocol requirement, not a bug
4. **Tool loop context preservation** — If the user message disappears from the messages list in round 2 of tool calls, the LLM loses conversation context. The fix: explicitly retain the current user message in compressed history
5. **Lightweight architecture choices** — SQLite + FastAPI + React enables shipping a functional full-stack product in a short time

---

## 许可证 / License

[MIT](LICENSE)
