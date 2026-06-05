# DeepSeek Chat

> 聊天是入口，Agent 是本质。| Chat is the entry. Agent is the essence.

DeepSeek Chat 是一个开源的 AI 对话平台，但它远不止是一个聊天界面。它的内核是一个不断演进的 Agent 架构 —— 从简单的问答到工具使用，从工具使用到任务规划，从任务规划到长期记忆，每一步都在让 AI 更接近一个真正理解你的伙伴。

DeepSeek Chat is an open-source AI chat platform, but it's much more than a chat UI. Under the hood is an evolving Agent architecture — from simple Q&A to tool use, from tool use to task planning, from task planning to long-term memory. Each step brings AI closer to being a companion that truly understands you.

---

## 设计哲学 / Design Philosophy

### Chat 是入口，不是终点

用户看到的是一个聊天界面，输入文字，得到回复。但每一次对话的背后，是一个多层 Agent 系统在工作：

```
用户看到的          系统在做的事情
─────────          ────────────────
"北京明天天气？"    → Tool Router 识别意图 → 匹配天气工具 → 执行 → 返回结果
"帮我分析这个文件"  → Planner 拆解步骤 → 读文件 → 分析 → 输出结论
"还记得我喜欢什么吗" → Honcho 记忆检索 → 语义匹配 → 融入上下文
```

聊天是用户与 AI 最自然的交互方式。我们相信**最好的界面就是没有界面** —— 不是让用户学习复杂的操作，而是让 Agent 理解用户想要什么，然后去做。

### Agent 能力的三个演进阶段

```
Phase 1: 对话           Phase 2: 工具               Phase 3: 自主
Converse               Use Tools                  Autonomy
   │                       │                          │
   ├─ 流式对话              ├─ Tool Router (21 tools)   ├─ Planner 任务规划
   ├─ Thinking 推理可视化    ├─ MCP Gateway              ├─ Sandbox 代码执行
   ├─ 多会话管理            ├─ 并发工具执行              ├─ 长期记忆 (Honcho)
   └─ 上下文感知            └─ 工具审批链               └─ 主动对话
```

我们目前已完成 Phase 1 和 Phase 2，正在推进 Phase 3。Chat 是这一切的用户界面，但真正的价值在于 Agent 如何在后台理解、规划和执行。

### 我们的愿景

AI 的价值不仅在于回答问题，更在于**持续的陪伴和深度的理解**。

我们不是在做另一个 ChatGPT 壳，而是在构建一个**了解你、记得你、陪伴你**的 AI 伙伴。它应该：
- 记住你的偏好和习惯，不需要你每次都重复
- 在合适的时机主动找你，像一个老朋友
- 跨设备无缝跟随，手机和电脑上的它是同一个
- 数据完全私有，部署在你自己的服务器上

---

## 当前能力 / Current Capabilities

### Agent 核心

| 能力 | 说明 | 状态 |
|------|------|------|
| **Tool Router** | 语义路由引擎，21 个工具自动匹配用户意图 | ✅ |
| **Tool Loop** | 多轮工具循环，支持复杂工作流 | ✅ |
| **Planner** | LLM 驱动任务规划，将目标拆解为可执行步骤 | ✅ |
| **Sandbox** | 安全 Python 代码执行，数据分析与图表生成 | ✅ |
| **长期记忆** | Honcho (pgvector + Redis)，跨会话记忆 + 语义检索 | ✅ |
| **MCP Gateway** | 标准化工具接入，兼容 MCP 协议 | ✅ |
| **Thinking 可视化** | DeepSeek V4 推理过程实时展示 | ✅ |

### 工具系统 (21 tools)

**内置工具 (8):**

| 工具 | 说明 |
|------|------|
| web_search | 实时网络搜索 (Tavily) |
| read_file | 文件读取 (PDF / MD / TXT / 代码) |
| describe_image | 图片识别 (Claude Sonnet Vision) |
| get_weather | 天气查询 |
| get_time | 时间/时区查询 |
| get_trends | 微博/知乎热搜 |
| search_bilibili | B站内容搜索 |
| execute_python | Python 代码沙箱 |

**MCP 工具 (13):** Tavily 搜索套件 + Sequential Thinking + Puppeteer 浏览器自动化

### 对话体验

- DeepSeek V4 Flash / Pro 双模型一键切换
- SSE 流式渲染 + 工具调用可视化
- 多会话管理 + 上下文自动压缩
- 自定义系统提示词 + 回复风格
- 附件上传 + 文件引用

---

## 架构 / Architecture

```
┌─────────────────────────────────────────────────┐
│         React SPA (TypeScript + Vite)             │
│      SSE streaming · Tool Cards · Settings        │
│               ↑ 用户看到的"聊天"                    │
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
│               ↑ Agent 的核心大脑                   │
└───┬────────┬──────────┬───────────┬─────────────┘
    │        │          │           │
┌───▼──┐ ┌───▼────┐ ┌───▼────┐ ┌───▼──────────┐
│Bridge│ │  Tool  │ │ Memory │ │  File System  │
│DS V4 │ │  8+13  │ │ Honcho │ │   Manager     │
└──────┘ └────────┘ └────────┘ └───────────────┘
```

**分层说明：**
- **Portal 层** — 用户界面，也是唯一的入口。支持 SSE 流式、工具卡片、暗色模式
- **Engine 层** — Agent 的编排层。ChatHandler 管理对话流程，Tool Router 做语义路由，Planner 拆解复杂任务
- **Service 层** — Bridge (LLM 协议适配)、Tool Executor (并发执行)、Memory (跨会话记忆)、File System (文件管理)
- **Data 层** — SQLite 持久化，DeepSeek API 直连，Tavily 搜索

---

## 快速开始 / Getting Started

### 前置条件

- Python 3.10+
- Node.js 18+ (仅前端开发)
- DeepSeek API Key
- Tavily API Key (搜索)
- ZenMux API Key (图片识别)

### 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | ✅ | DeepSeek V4 API 密钥 |
| `TAVILY_API_KEY` | ✅ | Tavily 搜索 API |
| `ZENMUX_API_KEY` | ✅ | ZenMux API (图片识别) |
| `CONVEY_TOKEN_SECRET` | - | Token 签名密钥，自动生成 |
| `CONVEY_PORT` | - | 端口，默认 3000 |

### 安装运行

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

### Nginx 反代 (可选)

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

## Agent 设计演进路线 / Agent Evolution Roadmap

这不是一个"加功能"的路线图，而是一个 Agent 能力的演进路径。每一步都在让 Agent 更自主、更理解用户、更像一个伙伴。

| 阶段 | 能力 | 当前 |
|------|------|------|
| **对话** | 流式对话、Thinking 可视化、多会话管理 | ✅ 已完成 |
| **工具使用** | Tool Router、21 工具、MCP Gateway、并发执行 | ✅ 已完成 |
| **任务规划** | Planner 拆解 + Sandbox 执行 + Tool Loop | ✅ 已完成 |
| **记忆持久化** | Honcho 长期记忆、语义检索、上下文融合 | ✅ 已完成 |
| **人格系统** | 角色/人格切换 (6 Persona)、自定义回复风格 | ✅ 已完成 |
| **主动对话** | AI 根据记忆主动发起话题、情境感知提醒 | 🚧 规划中 |
| **跨设备同步** | 手机/电脑无缝切换，对话和记忆完整跟随 | 🚧 规划中 |
| **端侧运行** | 本地推理，断网也能用，数据不出设备 | 🔮 远期愿景 |

---

## 与同类项目的区别 / What Makes This Different

| | DeepSeek Chat | 典型 ChatGPT 壳 |
|---|---|---|
| **定位** | Agent 架构实验场 | API 转发 + UI |
| **设计思路** | Agent 能力演进 → 聊天自然浮现 | 先做聊天界面 → 再加功能 |
| **记忆系统** | Honcho 长期记忆 + 语义检索 | 无，或简单上下文 |
| **工具系统** | 21 工具 + Router + Planner + Sandbox | 最多一个搜索插件 |
| **代码沙箱** | 安全执行，数据分析，图表生成 | 无 |
| **隐私** | 自托管，数据完全私有 | 依赖第三方平台 |
| **目标** | 成为懂你的 AI 伙伴 | 替代 ChatGPT 界面 |

---

## 许可证 / License

[MIT](LICENSE)
