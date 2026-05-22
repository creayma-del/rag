# 前端说明文档

## 项目概述

基于 Vue 3 Composition API 构建的 RAG 知识库 Web 前端，采用组件化 + Composables 架构，实现文档管理、知识库构建、对话问答和系统设置等功能。

### 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 框架 | Vue 3 + Composition API | `<script setup>` + TypeScript |
| 构建工具 | Vite 5 | 极速 HMR 开发体验 |
| 状态管理 | Pinia | 轻量级响应式状态 |
| 路由 | Vue Router 4 | 含认证导航守卫 + Token 过期检测 |
| UI 组件库 | Element Plus 2.9 | 企业级组件库 |
| 图标 | @element-plus/icons-vue | 统一图标方案 |
| HTTP 客户端 | Axios | 自动重试 + Token 注入 + 401 拦截 |
| Markdown 渲染 | marked + DOMPurify | AI 回复富文本展示 + XSS 防护 |
| 样式方案 | Scoped CSS + CSS Variables | 组件级样式隔离 |

## 目录结构

```text
frontend/
├── src/
│   ├── api/
│   │   └── index.ts              # Axios 封装（拦截器/重试/认证/Token管理）
│   ├── router/
│   │   └── index.ts              # 路由表 + 认证守卫 + Token 过期检测
│   ├── stores/
│   │   └── settings.ts           # Pinia 全局设置 Store（localStorage 持久化）
│   ├── types/
│   │   └── chat.ts               # 共享类型定义
│   ├── composables/              # 组合式函数（业务逻辑层）
│   │   ├── useChat.ts            # 聊天核心逻辑（流式/普通双模式）
│   │   ├── useSessions.ts        # 会话管理
│   │   ├── useDocuments.ts       # 文档管理 + 向量库操作
│   │   └── useSettingsForm.ts    # 设置表单逻辑
│   ├── views/                    # 路由页面（编排层）
│   │   ├── Chat.vue              # 对话页
│   │   ├── Documents.vue         # 文档管理页
│   │   ├── Settings.vue          # 系统设置页
│   │   └── Login.vue             # 登录页
│   ├── components/               # 通用组件
│   │   ├── chat/                 # 对话子组件
│   │   │   ├── ChatMessage.vue   # 消息卡片（Markdown渲染+检索详情）
│   │   │   ├── ChatInput.vue     # 输入框
│   │   │   ├── SessionSidebar.vue # 会话列表侧边栏
│   │   │   └── SettingsSidebar.vue # 设置面板侧边栏
│   │   ├── documents/            # 文档管理子组件
│   │   │   ├── DocumentCard.vue
│   │   │   ├── DocumentList.vue
│   │   │   ├── DocumentPreviewDialog.vue
│   │   │   ├── KnowledgeBaseStatus.vue
│   │   │   └── UploadDropZone.vue
│   │   ├── settings/             # 设置子组件
│   │   │   ├── ApiKeysSection.vue
│   │   │   ├── ModelListSection.vue
│   │   │   ├── ModelParamsSection.vue
│   │   │   ├── RagParamsSection.vue
│   │   │   └── SystemInfoSection.vue
│   │   └── ErrorBoundary.vue     # 错误边界
│   ├── styles/
│   │   └── global.css            # 全局设计系统
│   ├── App.vue                   # 根组件（导航栏+退出登录）
│   ├── main.ts                   # 应用入口
│   └── env.d.ts                  # 环境类型声明
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
└── tsconfig.node.json
```

## 架构设计

### 组件树

```
App.vue（全局导航栏 + 退出登录按钮）
├── ErrorBoundary
└── <router-view>
    ├── Login.vue                    # /login
    ├── Chat.vue                     # /chat（编排层）
    │   ├── SessionSidebar.vue       # 会话列表（大屏常驻/小屏抽屉）
    │   ├── ChatMessage.vue × N      # 消息卡片
    │   ├── ChatInput.vue            # 输入框
    │   └── SettingsSidebar.vue      # 设置面板（大屏常驻/小屏抽屉）
    ├── Documents.vue                # /documents
    │   ├── UploadDropZone.vue
    │   ├── DocumentList.vue
    │   ├── KnowledgeBaseStatus.vue
    │   └── DocumentPreviewDialog.vue
    └── Settings.vue                 # /settings
        ├── ApiKeysSection.vue
        ├── ModelListSection.vue
        ├── ModelParamsSection.vue
        ├── RagParamsSection.vue
        └── SystemInfoSection.vue
```

### 数据流

```
用户操作 → 子组件 $emit
  → 页面组件（编排层）
  → Composable（业务逻辑）
  → API 层（axios / fetch）
  → 后端服务
  → 响应数据回流
  → Composable 更新状态
  → 组件响应式渲染
```

### 架构分层

| 层 | 职责 | 示例 |
|----|------|------|
| **Views**（页面编排层） | 组装子组件，桥接 Composables | `Chat.vue` 组合 SessionSidebar + ChatMessage + ChatInput |
| **Components**（子组件） | 纯 UI 展示 + 事件抛出 | `ChatMessage.vue` 渲染消息卡片 |
| **Composables**（业务逻辑层） | 状态管理 + API 调用 + 副作用 | `useChat()` 管理消息列表、流式响应 |
| **Stores**（全局状态） | 跨页面共享配置 | `settingsStore` 管理模型/参数 |
| **API 层** | HTTP 请求封装 | `api.query()`、`api.uploadDocument()` |

## 路由与认证

### 路由表

| 路径 | 组件 | 说明 |
|------|------|------|
| `/login` | Login.vue | 公开页面，无需认证 |
| `/chat` | Chat.vue | 对话页（需认证） |
| `/documents` | Documents.vue | 文档管理页（需认证） |
| `/settings` | Settings.vue | 系统设置页（需认证） |
| `/` | → 重定向 `/chat` | |

### 认证守卫

```typescript
router.beforeEach((to) => {
  if (to.meta.public) return true           // 公开页面放行
  if (!isAuthenticated()) {                 // 检查 Token（含过期检测）
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  return true
})
```

- Token 存储在 `localStorage`，含 JWT 过期时间检测
- Axios 拦截器自动注入 `Authorization: Bearer <token>`
- 后端返回 401 时自动清除 Token 并跳转 `/login`
- 全局监听 `auth:unauthorized` 事件统一处理认证失效

## 页面说明

### Chat.vue — 对话页（编排层）

精简编排层，不包含具体 UI 实现：

- 使用 `useChat()` 管理消息和问答逻辑
- 使用 `useSessions()` 管理会话列表
- 共享 `currentSessionId` ref，确保 useChat 和 useSessions 操作同一引用
- 渲染 4 个子组件，通过 props/events 单向数据流通信
- 大屏：SessionSidebar 和 SettingsSidebar 常驻显示；小屏：抽屉式弹出
- 流式模式下由占位消息提供打字动画反馈，非流式模式显示独立加载指示器

### Documents.vue — 文档管理页

- 使用 `useDocuments()` 管理文档 CRUD
- 使用 `useVectorStore()` 管理知识库构建
- 支持拖拽上传、多文件上传、上传进度条
- 文档搜索过滤、预览弹窗
- 模型预热：单个预热 + 全部本地模型批量预热（轮询状态）
- 知识库状态展示与构建

### Settings.vue — 系统设置页

- RAG 参数配置（Chunk Size/Overlap、Embedding/Reranker 模型）
- 云端模型 API Key 配置与脱敏展示
- 对话参数（Temperature/Max Tokens/Top K）
- 模型列表展示（云端 + 本地分组）
- 未保存变更检测 + 页面关闭提示

### Login.vue — 登录页

- 密码输入框 + 登录按钮
- JWT Token 存储与认证
- 登录后跳转到 `redirect` 参数指定的页面

## Composables

### useChat()

对话核心逻辑，支持外部传入 `currentSessionId` ref：

**状态**：`messages`、`loading`、`inputText`、`connected`、`vectorStoreExists/stale`、`models`、`useStreaming`、`showRetrievalResults`、`quickTips`、`abortController`、`lastQuestion`

**方法**：
- `sendMessage(sessionOps)` — 发送消息（自动中止旧流式请求、ensureSession、流式/普通双模式）
- `stopStreaming(targetMsgId?)` — 停止流式响应（AbortController + 清理占位消息）
- `regenerateMessage(msgIdx)` — 重新生成指定消息
- `regenerateInterrupted()` — 断点续传（恢复最后一条被中断的消息）
- `copyMessage(text)` — 复制消息内容
- `toggleRetrievalDetails(idx)` — 展开/折叠检索结果
- `scrollToBottom()` — 滚动到底部
- `checkConnection()` / `loadModels()` / `checkVectorStore()` / `ensureModelReady()`

**流式处理流程**：
```
fetch POST /api/query/stream
  → ReadableStream 逐行读取
  → 解析 SSE 事件边界（\n\n）
  → 合并多行 data: 字段
  → JSON 解析 → token 追加到当前 AI 消息
  → data: [DONE] 标记结束
  → 流式失败/无内容时自动降级到普通请求
```

**消息 ID 追踪**：所有消息通过唯一 ID 管理，支持通过 ID 精确查找和更新，避免索引偏移问题。

### useSessions()

会话管理，提供约 10 个响应式状态和方法：

**状态**：`sessions`、`currentSessionId`、`loadingSessions`、`sessionsSearch`、`filteredSessions`（computed）、`sessionsDisplayCount`

**方法**：
- `loadSessions()` — 加载会话列表（加载后自动恢复最近会话）
- `createNewSession(messageCount)` — 新建会话（含确认弹窗）
- `loadSession(id)` — 加载会话详情（含历史消息，snake_case→camelCase 映射）
- `deleteSession(id)` — 删除会话（返回 `{ wasCurrent }` 标识）
- `renameSession(id, title)` — 重命名会话
- `loadMoreSessions()` — 加载更多（分页展示，每页 20 条）

### useDocuments()

文档管理，导出 `useDocuments()` 和 `useVectorStore()`：

**useDocuments 状态**：`documents`、`loadingDocs`、`uploadingFile`、`uploadProgress`、`docSearch`、`isDragOver`、`filteredDocuments`、`uploadExtensions`、`previewVisible/loading/fileName/content/fileSize/lineCount/error/message`

**useDocuments 方法**：
- `loadDocuments()` — 加载文档列表
- `uploadFile(file)` / `uploadFiles(files)` — 单文件/批量上传
- `deleteDocument(filename)` — 删除文档
- `previewDocument(filename)` — 预览文档
- `formatSize(bytes)` — 格式化文件大小

**useVectorStore 状态**：`building`、`preloading`、`preloadingAll`、`vectorStoreExists`、`vectorStoreStale`

**useVectorStore 方法**：
- `checkStatus()` — 检查向量库状态
- `build(documentCount)` — 构建向量库（含文档数量校验、409 冲突处理）
- `preloadModel(modelName)` — 预热指定模型
- `preloadAll(localModels)` — 预热所有本地模型

### useSettingsForm()

设置表单逻辑：

**状态**：`apiKeys`（输入值）、`apiKeysMasked`（脱敏展示）、`apiKeysConfigured`（是否已配置）、`models`、`saving`、`activeApiKey`、`apiKeySearch`、`hasUnsavedChanges`、`systemConfig`

**方法**：
- `loadModels()` / `loadApiKeyStatus()` / `loadSystemConfig()` — 加载数据
- `saveAllSettings()` — 保存所有设置（API Keys + 系统配置）
- `markDirty()` — 标记未保存变更
- `hasKey(modelName)` — 检查模型是否已配置 API Key

**特性**：
- RAG 核心参数变更时提示用户重建知识库
- chunk_overlap 不能大于等于 chunk_size 校验
- 页面关闭前未保存提示（`beforeunload` 事件）

## 类型定义

`src/types/chat.ts` 定义共享类型：

```typescript
interface RetrievalDoc {
  index: number
  source: string
  score?: number
  content_preview?: string
  content?: string
}

interface ChatMessage {
  id: string
  role: 'user' | 'ai'
  content: string
  retrievalInfo: RetrievalDoc[]
  rerankInfo: RetrievalDoc[]
  showRetrievalDetails: boolean
  isInterrupted?: boolean
}

interface ModelInfo {
  name: string
  description?: string
  model?: string
}

interface ModelsData {
  cloud_models: ModelInfo[]
  local_models: ModelInfo[]
}

interface SessionItem {
  session_id: string
  title: string
  updated_at: string
  message_count: number
}

interface QuickTip {
  id: number
  text: string
}
```

## Store

### settingsStore (Pinia)

全局配置状态，跨 Chat/Settings 页面共享，自动持久化到 `localStorage`：

| 状态 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `selectedModel` | `string` | `'local'` | 当前选择的模型 |
| `temperature` | `number` | `0.1` | 生成温度 |
| `maxTokens` | `number` | `4096` | 最大 Token |
| `topK` | `number` | `5` | 检索返回数 |
| `useReranker` | `boolean` | `false` | 是否启用 Reranker |
| `rerankerTopN` | `number` | `3` | 重排保留数 |

## API 层

`src/api/index.ts` — Axios 实例封装：

- `baseURL: '/api'`，通过 Vite 代理到后端
- `timeout: 120000`（2 分钟，查询接口 10 分钟）
- **请求拦截器**：自动注入 `Authorization: Bearer <token>`
- **响应拦截器**：401 → 清除 Token + 派发 `auth:unauthorized` 事件 → 跳转登录
- **GET 请求自动重试**：最多 3 次，指数退避，仅网络/超时错误
- **Token 管理**：`getToken()`、`setToken()`、`clearToken()`、`isAuthenticated()`（含 JWT 过期检查）

API 方法按功能分类：

| 分类 | 方法 | 说明 |
|------|------|------|
| 认证 | `login(password)` | 登录获取 Token |
| 认证 | `verifyAuth()` | 验证 Token |
| 系统 | `healthCheck()` | 健康检查 |
| 模型 | `getModels()` | 获取模型列表 |
| 模型 | `preloadModels()` | 预加载默认模型 |
| 模型 | `preloadModelRuntime(params)` | 预热指定模型 |
| 模型 | `getPreloadStatus(model)` | 查询预热状态 |
| 配置 | `getConfig()` | 获取配置 |
| 配置 | `updateConfig(params)` | 更新 API Key |
| 配置 | `getApiKeyStatus()` | 获取 API Key 状态（脱敏） |
| 配置 | `getSystemConfig()` | 获取系统配置 |
| 配置 | `updateSystemConfig(params)` | 更新系统配置 |
| 文档 | `listDocuments()` | 文档列表 |
| 文档 | `uploadDocument(file, onProgress)` | 上传文档 |
| 文档 | `deleteDocument(filename)` | 删除文档 |
| 文档 | `previewDocument(filename)` | 预览文档 |
| 向量库 | `buildVectorStore()` | 构建知识库 |
| 向量库 | `getBuildStatus()` | 构建状态 |
| 向量库 | `getVectorStoreStatus()` | 知识库状态 |
| 问答 | `query(params)` | 普通问答 |
| 问答 | `queryStreamPost(params, signal)` | 流式问答（原生 fetch） |
| 会话 | `createSession(title?)` | 创建会话 |
| 会话 | `listSessions()` | 会话列表 |
| 会话 | `getSession(id)` | 会话详情 |
| 会话 | `updateSessionTitle(id, title)` | 更新标题 |
| 会话 | `deleteSession(id)` | 删除会话 |
| 会话 | `clearAllSessions()` | 清空所有会话 |

## 样式系统

`src/styles/global.css` 定义全局设计变量：

```css
:root {
  --bg-primary: #0f0c29;
  --bg-secondary: #302b63;
  --bg-tertiary: #24243e;
  --glass-bg: rgba(255, 255, 255, 0.05);
  --accent-primary: #00d4ff;      /* 主色调 */
  --accent-secondary: #7b2cbf;     /* 辅色调 */
  --accent-tertiary: #00f593;      /* 成功色 */
  --accent-danger: #ff6b6b;
  --accent-warning: #ffd93d;
  --text-primary: #ffffff;
  --text-secondary: #b8c5d6;
  --text-muted: #6b7280;
}
```

- 科技感玻璃态风格（Glassmorphism）
- 动态渐变背景（`@keyframes gradientShift`）
- Element Plus 全局覆盖（Input/Select/Button/Table/Tag/Slider 等）
- 自定义滚动条渐变样式
- `scoped` 组件级样式隔离，子组件独立维护自身样式
- 响应式断点：1024px（侧边栏抽屉化）、640px（紧凑布局）

## 启动方式

### 安装依赖

```bash
cd frontend
pnpm install
```

### 开发模式

```bash
pnpm dev
```

默认启动 `http://localhost:5173`。

### 生产构建

```bash
pnpm build
```

产物输出到 `dist/`。

### 类型检查

```bash
pnpm typecheck
```

### 代码检查

```bash
pnpm lint        # 自动修复
pnpm lint:check  # 仅检查
```

## 联调说明

`vite.config.ts` 开发代理配置：

```typescript
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

## 开发建议

- 新增对话功能时，优先在 `useChat` composable 中添加逻辑，保持 View 编排层纤薄
- 修改 API 接口字段时，同步更新 `src/types/chat.ts` 类型定义
- 新增 API 调用时，遵循现有 `api/index.ts` 的封装模式
- 样式使用 CSS 变量（`var(--accent-primary)` 等），保持主题一致性
- 子组件通过 Props/Emits 通信，禁止直接修改 Props
- 流式请求使用原生 `fetch`（非 Axios），需手动解析 SSE 事件边界
