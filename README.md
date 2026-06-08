# DeepSeek Chat

> **Agent 是手段，更好的聊天是目的。** Agent is the means. Better conversation is the goal.

DeepSeek Chat 不是"又一个 ChatGPT 壳"。它是一个**聊天交互质量的算法实验场**——用 Agent 架构作为实验工具，系统性地探索如何让 AI 聊天更高效、更稳定、更快速、更真实。

DeepSeek Chat is not "yet another ChatGPT wrapper." It's an **algorithmic laboratory for conversation quality** — using Agent architecture as experimental apparatus to systematically explore what makes AI conversations more efficient, stable, fast, and authentic.

---

## 核心理念 / Core Philosophy

### 聊天不是"输入→输出"，而是多层 Agent 协作的结果

每一次用户看到的消息回复，背后都有一个 Agent 系统在实时决策：

- 这段对话需要搜索吗？需要读文件吗？需要查记忆吗？
- 当前的 context 组合是否最优——记忆放前面还是放后面？
- 该用 Flash 快速回复，还是该启动 Pro 深度推理？
- 上一轮工具结果是否值得保留在上下文里？

**这些决策直接影响聊天质量，但没有"标准答案"。** DeepSeek Chat 存在的意义就是通过对照实验找到更好的答案。

### 和 Convey App 的关系

```
deepseek-chat (Web 实验场)              Convey App (iOS/macOS 产品)
══════════════════════════              ══════════════════════════
探索"怎么做最好"                       交付"最好的体验"
有 Planner/Tool Router 做对照实验       只取实验验证过的最优方案
可以失败、可以推倒重来                  稳定优先
面向算法验证速度                        面向用户体验质量
```

---

## 七大研究方向 / Seven Research Tracks

### 1. 高效 — Context 最优组合

**问题**：DeepSeek 上下文窗口很大。但塞满不等于质量高。什么信息、什么顺序、什么格式产生最佳输出？

| 实验方向 | 待验证假设 |
|----------|-----------|
| System Prompt 位置 | 放在消息列表最前 vs 最后，影响回复一致性吗？ |
| 记忆注入策略 | 独立 system message vs 拼在 user message 末尾，RAG 召回质量如何变化？ |
| 工具定义位置 | 每次请求都发 vs 缓存复用，token 消耗差多少？ |
| 历史压缩策略 | 摘要 vs 截断 vs 关键句提取 vs 直接丢弃 — 各丢多少信息？ |
| Token <-> 质量曲线 | 每减少 10% token 消耗，回复质量下降多少？ |

**可量化指标**：回复相关性评分 · 工具调用准确率 · token 消耗/有效回复比 · reasoning_content 深度

---

### 2. 稳定 — 中断与恢复

**问题**：真实对话不是一次性的。用户说一半暂停、改主意、补充信息，AI 如何不断不乱？

| 实验方向 | 待验证假设 |
|----------|-----------|
| 用户修正 | 用户说"等等，不对"→ AI 能否回退部分推理并基于修正重新开始？ |
| 消息追加 | 用户发出一条消息，中途又发"补充一点..."→ 合并输入再推理 vs 两条独立消息 |
| 网络恢复 | SSE 断连后从断点续传 vs 重新请求，延迟差多少？ |
| 用户打断 | AI 正在生成 → 用户打断 → 保留已推理内容作为上下文重新应答 |
| 多轮连贯性 | 10 轮后模型是否还遵循初始 system prompt 中的约束？ |

**可量化指标**：中断后恢复的连贯性评分 · 用户补充信息的利用率 · 长对话人格漂移距离

---

### 3. 快速 — 更少资源、更复杂任务

**问题**：同样的任务，能不能用更少的 token、更少的 API 调用、更低的延迟完成？

| 实验方向 | 待验证假设 |
|----------|-----------|
| 模型路由 | 简单问题跳过 thinking mode → Flash → Pro 只用于复杂推理。阈值怎么定？ |
| 工具调用降级 | 先让 AI 判断"这个任务需要工具吗"，不需要则跳过 Tool Loop |
| 缓存复用 | system prompt + 工具定义做 prompt caching，能省多少延迟？ |
| 历史压缩 | 长对话中哪些消息可以安全丢弃？丢弃前后的回复质量对比 |
| 并发优化 | 多个工具并发执行 vs 串行，实际节省多少时间？ |

**可量化指标**：单次回复 token 消耗 · 端到端延迟 · 质量下降/token 节省比值 · API 调用次数

---

### 4. 长链路推理可视化 — 把"思考"变成体验

**问题**：DeepSeek V4 的 reasoning_content 是巨大优势，但用户看到的是空白等待。如何让推理过程增强而非打断体验？

| 实验方向 | 待验证假设 |
|----------|-----------|
| 实时推理展示 | 推理内容流式渲染 → 用户知道 AI 在"想"什么，等待感是否降低？ |
| 推理折叠 | 超过 N 字的推理自动折叠 → 想看的展开，不想看的略过 |
| 推理分段 | 长推理分多段展示，每段一个主题，方便用户跳读 |
| 推理中途引导 | 推理方向偏了 → 用户能否在中间插入反馈修正方向？ |
| 大上下文导航 | 100 万 token 上下文中，如何让用户感知"AI 用了哪些信息来生成这个回答"？ |

**可量化指标**：用户等待满意度 · 推理展开率 · 推理引导后的回复改善率

---

### 5. 记忆引用与需求挖掘 — 让记忆"可见"

**问题**：记忆不只是后台检索，而应该是对话体验的一部分。AI 应该主动引用记忆来挖掘真实需求。

| 实验方向 | 待验证假设 |
|----------|-----------|
| 记忆溯源 | AI 回复时标注"基于你之前提到的..."→ 用户信任度变化 |
| 需求挖掘 | 用户说"有点烦"→ AI 根据记忆知道在做项目 → 追问"是不是 Deadline 问题？" |
| 记忆矛盾检测 | 用户说"喜欢辣"但记忆有"不喜欢川菜"→ AI 主动澄清，用户满意度如何？ |
| 遗忘曲线 | 哪些记忆该衰减、哪些该强化？模拟人类记忆的自然规律 |
| 记忆可见性 | 用户可随时查看 AI 用了哪些记忆（类似 Claude 的透明设计） |

**可量化指标**：记忆引用准确率 · 需求挖掘深度评分 · 用户感知"AI 了解我"的程度

---

### 6. 拟人性格 — 一致性 + 不谄媚

**问题**：不是"AI 模仿某个角色"，而是 AI 展现出类人的性格深度——包括缺点和坚持。

| 实验方向 | 待验证假设 |
|----------|-----------|
| 人格漂移测试 | 同一人格 100 轮后 embedding 余弦距离变化 |
| 情境反应差异 | 高兴/困惑/坚持己见/承认错误 → 不同人格的表现不同 |
| 记忆驱动人格演变 | AI 记住用户偏好 → 逐渐调整说话方式 |
| 反谄媚机制 | AI 拒绝用户的频率 vs 用户满意度曲线 |
| 多角色对比 | 同一用户在不同人格下的满意度和使用深度差异 |

**可量化指标**：人格漂移距离 · 谄媚指数（同意错误观点的比例）· 人格一致性用户评分

---

### 7. 降幻觉 — 多策略对照

**问题**：DeepSeek V4 在什么场景下容易幻觉？什么手段最有效地降幻觉？

| 实验方向 | 待验证假设 |
|----------|-----------|
| 工具调用降幻觉 | 有 web_search 后有事实依据 → 幻觉率下降多少？ |
| 强制引用 | 要求 AI 每句话给出依据 → 幻觉是否显著下降？ |
| 推理链长度 | reasoning 越深入 → 幻觉越少？ |
| 交叉验证 | 同一问题问两次，比较输出一致性 — 自我矛盾率 |
| 领域差异 | 代码/事实/观点/创意 → 不同领域的幻觉模式不同 |
| 拒绝策略 | 不确定时拒绝回答 vs 尝试回答 → 准确率和用户满意度 tradeoff |
| self-consistency | 多次推理取多数一致的结果，成本 vs 准确率 |

**可量化指标**：事实准确率 · 自我矛盾率 · 拒答率/幻觉率 tradeoff 曲线

---

## 当前架构 / Architecture

实验场需要可替换的组件来跑对照实验。当前架构：

```
┌─────────────────────────────────────────────────┐
│         React SPA (TypeScript + Vite)             │
│      SSE streaming · Tool Cards · Context Panel   │
│               ↑ 实验结果的展示层                    │
└────────────────────┬────────────────────────────┘
┌────────────────────▼────────────────────────────┐
│          FastAPI Server (Python)                  │
│   Auth · Chat · Upload · Session · Context        │
└────────────────────┬────────────────────────────┘
┌────────────────────▼────────────────────────────┐
│        Conversation Engine (Python)               │
│  ChatHandler · Tool Loop · Tool Router · Planner  │
│               ↑ 实验变量的控制层                    │
└───┬────────┬──────────┬───────────┬─────────────┘
    │        │          │           │
┌───▼──┐ ┌───▼────┐ ┌───▼────┐ ┌───▼──────────┐
│Bridge│ │  Tool  │ │ Memory │ │  File System  │
│DS V4 │ │  21个  │ │ Honcho │ │   Manager     │
│直连  │ │ 可替换  │ │ 可替换  │ │   可替换       │
└──────┘ └────────┘ └────────┘ └───────────────┘
```

**设计原则**：Bridge / Tool / Memory / File System 四个模块都可替换。对比实验时只需要切换组件即可。

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
git clone https://github.com/JackieL67/deepseek-chat.git
cd deepseek-chat

# 构建前端
cd convey-portal-ui
pnpm install && pnpm build
cd ..

# 配置
cp .env.example .env
# 编辑 .env 填入 API keys

# 启动
source .env
python3 user-portal/server.py
```

访问 `http://localhost:3000`

---

## 技术栈 / Tech Stack

| 模块 | 技术 | 说明 |
|------|------|------|
| Frontend | React 18 + TypeScript + Vite | 实验 UI |
| Backend | FastAPI + Uvicorn (async) | SSE 流式 |
| Database | SQLite (aiosqlite) | 轻量持久化 |
| AI Model | DeepSeek V4 Pro (streaming + reasoning + tool_calls) | 核心实验对象 |
| Vision | Claude Sonnet (via zenmux) | 图片理解 |
| Search | Tavily API | 实时搜索 |
| Memory | Honcho (pgvector + Redis) | 长期记忆 |
| Embedding | text-embedding-3-small (1536-d) | 语义向量 |

---

## 许可证 / License

[MIT](LICENSE)
