# RAG 个人知识库 Q&A System

前后端分离的个人知识库 RAG（Retrieval-Augmented Generation）问答系统。支持上传多种格式文档、构建向量知识库，并使用云端或本地大模型进行检索增强生成问答。

## 项目架构

```
Rag/
├── backend/                    # FastAPI 后端服务
│   ├── api.py                  # API 路由入口（22 个端点）
│   ├── config.py               # 全局配置与密钥管理
│   ├── cli.py                  # CLI 命令行工具
│   ├── main.py                 # 本地交互式问答入口
│   ├── requirements.txt        # Python 依赖
│   ├── .env / .env.example     # 环境变量配置
│   └── src/
│       ├── qa_engine.py        # RAG 问答引擎（检索→重排→生成）
│       ├── vector_store.py     # Chroma 向量数据库管理
│       ├── document_loader.py  # 多格式文档加载与切分
│       ├── auth.py             # JWT 认证 + API Key 加密
│       ├── chat_history.py     # 会话历史管理（原子写入+并发锁）
│       └── trace_logger.py     # Pipeline 追踪日志
├── frontend/                   # Vue 3 前端
│   ├── src/
│   │   ├── api/index.ts        # Axios API 封装层
│   │   ├── router/index.ts     # 路由配置（含认证守卫+Token 过期检测）
│   │   ├── stores/settings.ts  # Pinia 全局设置状态
│   │   ├── types/chat.ts       # TypeScript 类型定义
│   │   ├── composables/        # 组合式函数（Hooks）
│   │   │   ├── useChat.ts      # 聊天逻辑（流式/普通双模式）
│   │   │   ├── useSessions.ts  # 会话管理
│   │   │   ├── useDocuments.ts # 文档管理 + 向量库操作
│   │   │   └── useSettingsForm.ts # 设置表单逻辑
│   │   ├── views/              # 路由页面
│   │   │   ├── Chat.vue        # 对话页（编排层）
│   │   │   ├── Documents.vue   # 文档管理页
│   │   │   ├── Settings.vue    # 系统设置页
│   │   │   └── Login.vue       # 登录页
│   │   ├── components/         # 通用组件
│   │   │   ├── chat/           # 对话子组件
│   │   │   │   ├── ChatMessage.vue
│   │   │   │   ├── ChatInput.vue
│   │   │   │   ├── SessionSidebar.vue
│   │   │   │   └── SettingsSidebar.vue
│   │   │   ├── documents/      # 文档管理子组件
│   │   │   ├── settings/       # 设置子组件
│   │   │   └── ErrorBoundary.vue
│   │   └── styles/global.css   # 全局设计系统
│   ├── package.json
│   └── vite.config.ts
├── data/                       # 运行数据（向量库/会话/加密密钥）
├── documents/                  # 用户上传文档目录
├── start.sh                    # 启动脚本（含依赖检查/端口检测/日志/PID管理）
├── stop.sh                     # 停止脚本
└── README.md
```

## 核心能力

### 文档管理
- 支持 13 种文档格式：TXT、MD、MARKDOWN、PDF、DOCX、CSV、JSON、HTML、XML、YAML、ZIP
- 拖拽上传 + 点击上传，支持多文件批量上传
- ZIP 压缩包自动解包并读取内部文档（安全校验：路径遍历拦截、成员数/解压大小限制）
- 文档预览（文本类直接预览，二进制/压缩包显示元信息）
- 上传进度条实时反馈
- 搜索过滤 + 总大小统计
- 删除文档时自动同步清理向量库中对应 chunks

### 知识库构建
- 基于 Chroma 向量数据库持久化存储
- Embedding 模型：`sentence-transformers/all-MiniLM-L6-v2`
- 文档增量检测：SHA256 内容哈希快照对比，仅在文档变更时重建
- 增量构建：仅有新增文档时增量追加，避免全量重建
- 全量重建时备份/恢复：构建前备份旧库，失败时自动回滚
- 构建并发保护（409 冲突响应），避免重复构建
- 构建状态查询（running/completed/failed）
- 知识库三态：`exists`（存在）/ `current`（最新）/ `stale`（过期）

### 对话问答
- **双模式**：流式（SSE）/ 普通请求
- **流式断点续传**：停止后可继续生成，不丢失已有内容
- **消息操作**：复制、重新生成、继续生成
- **检索增强**：向量检索 + 可选 Reranker 重排序
- **检索结果展示**：折叠/展开检索到的文档片段，含来源和相关性分数
- **Reranker 提示**：标记经过重排序的结果
- **快捷提示**：预设问题一键发送
- **多轮对话**：会话历史保存与恢复（最近 10 轮上下文）
- **流式降级**：流式请求失败时自动降级到普通请求

### 模型支持
| 类别 | 模型 | 说明 |
|------|------|------|
| 云端 | OpenAI GPT-4o Mini | 高性价比 |
| 云端 | 通义千问 Qwen-Plus | 阿里云 |
| 云端 | 智谱 GLM-4-Flash | 快速推理 |
| 云端 | Kimi Moonshot-v1-8k | 超长上下文 |
| 云端 | DeepSeek-V3 | 国产顶流 |
| 云端 | Groq Llama 3.3 70B | LPU 极速 |
| 云端 | Mistral Small | 欧洲领先 |
| 云端 | 百川 Baichuan4-Air | |
| 云端 | 阶跃星辰 Step-2 | |
| 云端 | 文心一言 | 百度千帆（OAuth 2.0） |
| 云端 | 硅基流动 DeepSeek-V3 | 模型聚合平台 |
| 本地 | Qwen2-0.5B | 低配置设备 |
| 本地 | Qwen2-1.5B | 默认本地模型 |
| 本地 | Qwen2.5-3B | 平衡性能 |
| 本地 | Qwen2-7B | 更高效果 |
| 本地 | Qwen2.5-7B | 大模型，延迟预热 |

### 安全机制
- **JWT 认证**：前端登录页 + Token 验证中间件（24h 有效期）
- **路由守卫**：未登录自动跳转 /login，Token 过期自动检测
- **密码配置**：`.env` 中 `AUTH_PASSWORD`，默认 `admin`
- **API Key 加密存储**：Fernet 对称加密（PBKDF2 派生密钥）持久化到 `data/encrypted_keys.json`
- **SSE Token 传递**：支持 URL 查询参数 `?token=` 方式传递认证信息
- **脱敏展示**：前端只显示 `sk-****xxxx` 格式的 API Key
- **占位值过滤**：`.env` 中 `your-*-api-key` 格式的占位值自动识别为未配置
- **登录速率限制**：5 分钟内最多 5 次登录尝试

### 会话管理
- 自动创建会话（首条消息自动标题）
- 会话列表（按更新时间倒序）
- 会话搜索/过滤
- 会话重命名/删除
- 点击加载历史对话
- 新建对话确认（有未保存消息时弹窗提示）
- 并发写入保护（会话级锁 + 原子文件写入）

### 可调参数
| 参数 | 默认值 | 范围 | 说明 |
|------|--------|------|------|
| Temperature | 0.1 | 0–2.0 | 生成随机性（0 = 贪心解码） |
| Max Tokens | 4096 | 256–8192 | 最大生成长度 |
| Top K | 5 | 1–10 | 检索返回文档数 |
| Reranker Top N | 3 | 1–10 | 重排序后保留数 |
| Chunk Size | 500 | — | 文档切分块大小 |
| Chunk Overlap | 50 | — | 切分重叠量 |
| Embedding Model | MiniLM-L6-v2 | — | 嵌入模型 |
| Reranker Model | bge-reranker-base | — | 重排模型 |

## 环境要求

- Python 3.9+
- Node.js 18+
- pnpm 8+

## 快速开始

### 1. 配置环境变量

```bash
cd backend
cp .env.example .env
# 编辑 .env，配置 AUTH_PASSWORD 和需要的云端 API Key
```

### 2. 安装依赖

```bash
# 后端
cd backend
pip3 install -r requirements.txt

# 前端
cd frontend
pnpm install
```

### 3. 启动服务

**方式一：一键启动（自动检查依赖、清理旧进程）**

```bash
./start.sh
```

**方式二：停止服务**

```bash
./stop.sh
```

支持环境变量：`PYTHON_BIN`（默认 python3）、`BACKEND_PORT`（默认 8000）、`FRONTEND_PORT`（默认 5173）

**方式三：分别启动**

```bash
# 终端 1：后端
cd backend
uvicorn api:app --reload --host 0.0.0.0 --port 8000

# 终端 2：前端
cd frontend
pnpm dev
```

### 4. 访问应用

- 前端：`http://localhost:5173`
- 后端 API：`http://localhost:8000`
- API 文档：`http://localhost:8000/docs`（Swagger UI）

### 5. 使用流程

1. 浏览器打开 `http://localhost:5173`，输入密码登录
2. 进入「文档管理」页面上传文档
3. 点击「构建知识库」
4. 进入「对话」页面选择模型并开始提问

## 前后端联调

前端通过 Vite 代理 `/api` 请求到 `http://localhost:8000`：

```typescript
// vite.config.ts
server: {
  port: 5173,
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
}
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/auth/login` | 登录获取 Token |
| GET | `/api/models` | 获取可用模型列表 |
| GET | `/api/config` | 获取当前配置 |
| PUT | `/api/config` | 更新配置 |
| GET | `/api/documents` | 获取文档列表 |
| POST | `/api/documents/upload` | 上传文档 |
| DELETE | `/api/documents/{filename}` | 删除文档 |
| POST | `/api/vectorstore/build` | 构建知识库 |
| GET | `/api/vectorstore/status` | 查询知识库状态 |
| GET | `/api/chat/sessions` | 获取会话列表 |
| POST | `/api/chat/sessions` | 创建会话 |
| GET | `/api/chat/sessions/{id}` | 获取会话详情 |
| PUT | `/api/chat/sessions/{id}` | 更新会话（重命名） |
| DELETE | `/api/chat/sessions/{id}` | 删除会话 |
| POST | `/api/query` | 普通问答 |
| POST | `/api/query/stream` | 流式问答（SSE） |
| GET | `/api/api-keys/status` | 获取 API Key 配置状态 |
| PUT | `/api/api-keys/{model}` | 更新指定模型 API Key |
| DELETE | `/api/api-keys/{model}` | 删除指定模型 API Key |

## 前端构建

```bash
cd frontend
pnpm build
```

## 注意事项

- 本地模型首次使用会自动从 Hugging Face 下载，需要网络连接
- 国内网络建议设置 `HF_ENDPOINT=https://hf-mirror.com` 加速下载
- 文档变更后知识库状态变为 `stale`，需要重新构建
- `langchain-chroma==0.1.2` 需与 `chromadb==0.5.5` 配对使用
- 大型本地模型（7B+）建议通过后台延迟预热加载，避免首次问答阻塞
- SSE 流式响应不支持标准 HTTP 认证头，需通过 URL `?token=` 参数传递
- 修改 `AUTH_PASSWORD` 后已加密的 API Key 将无法解密，需重新配置
- 本地模型 `temperature=0` 时自动使用贪心解码（`do_sample=False`）
