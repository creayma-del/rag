# 后端说明文档

## 项目概述

基于 FastAPI 构建的 RAG 知识库后端服务，负责文档处理、向量检索、问答生成与系统管理。

### 核心技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| Web 框架 | FastAPI 0.115 | 异步 HTTP API |
| 向量数据库 | ChromaDB 0.5.5 | 向量持久化存储 |
| LangChain 集成 | langchain-chroma 0.1.2 | Chroma 向量库封装 |
| Embedding | sentence-transformers / MiniLM-L6-v2 | 文本向量化 |
| Reranker | BAAI/bge-reranker-base | 检索结果重排序 |
| LLM 运行时 | langchain-huggingface / transformers | 云端+本地模型加载 |
| 认证 | PyJWT + Fernet (cryptography) | JWT Token + API Key 加密 |
| 配置管理 | python-dotenv | 环境变量加载 |

## 目录结构

```text
backend/
├── api.py                  # FastAPI 路由入口（22 个 API 端点）
├── config.py               # 全局配置类（模型/路径/密钥/持久化）
├── cli.py                  # 命令行工具（build/query/chat/models）
├── main.py                 # 交互式问答入口
├── requirements.txt        # Python 依赖清单
├── .env / .env.example     # 环境变量配置
└── src/
    ├── __init__.py         # 包初始化
    ├── auth.py             # 认证与加密模块
    ├── chat_history.py     # 会话历史管理（原子写入+并发锁）
    ├── document_loader.py  # 多格式文档加载与切分
    ├── qa_engine.py        # RAG 问答引擎核心
    ├── trace_logger.py     # Pipeline 追踪日志
    └── vector_store.py     # Chroma 向量库生命周期管理
```

## 核心模块详解

### `api.py` — API 路由入口

定义 22 个 REST API 端点，涵盖以下功能域：

#### 认证（Auth）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 密码登录，返回 JWT Token（含 IP 速率限制：5分钟5次） |
| GET | `/api/auth/verify` | 验证 Token 有效性 |

#### 系统健康
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查（公开，无需认证） |

#### 模型管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/models` | 获取所有模型列表（云端 + 本地） |
| GET | `/api/preload` | 后台预加载模型（GET 参数方式） |
| POST | `/api/preload` | 后台预加载模型（POST body 方式） |
| GET | `/api/preload/status` | 查询模型预热状态（idle/loading/ready/failed） |

#### 配置管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config` | 获取对话参数配置 |
| GET | `/api/config/keys` | 获取 API Key 列表（脱敏，占位值自动识别为未配置） |
| POST | `/api/config` | 更新模型 API Key（加密持久化，运行时缓存失效） |
| GET | `/api/config/system` | 获取完整系统配置 |
| POST | `/api/config/system` | 更新系统配置（变更时自动标记向量库失效或清除缓存） |

#### 文档管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/documents` | 获取文档列表 |
| POST | `/api/documents/upload` | 上传文档（含文件名校验、路径遍历防护） |
| DELETE | `/api/documents/{filename}` | 删除文档（同步清理向量库中对应 chunks） |
| GET | `/api/documents/preview/{filename}` | 预览文档（文本类直接返回，限 500KB） |

#### 向量库管理
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/vectorstore/build` | 构建/重建向量库（含并发锁保护，增量/全量自动判断） |
| GET | `/api/vectorstore/build/status` | 查询构建任务状态 |
| GET | `/api/vectorstore/status` | 查询向量库状态（exists/stale/documents_count） |

#### 问答（Query）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/query` | 普通问答（同步返回，含多轮对话历史、Reranker） |
| GET | `/api/query/stream` | 流式问答（SSE，GET 参数） |
| POST | `/api/query/stream` | 流式问答（SSE，POST body，推荐） |

#### 会话管理（Chat Sessions）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat/sessions` | 创建新会话 |
| GET | `/api/chat/sessions` | 获取会话列表（按 updated_at 降序） |
| GET | `/api/chat/sessions/{session_id}` | 获取会话详情（含全部消息） |
| PUT | `/api/chat/sessions/{session_id}/title` | 更新会话标题 |
| DELETE | `/api/chat/sessions/{session_id}` | 删除会话 |
| DELETE | `/api/chat/sessions` | 清空所有会话 |

#### 全局中间件
- **CORS**：允许所有来源
- **认证中间件**：除公开路径外，所有请求需携带有效 JWT；支持 `Authorization: Bearer` header 或 `?token=` URL 参数（SSE 兼容）；OPTIONS 预检请求放行
- **LangChain 遥测禁用**：启动时设置环境变量，避免 posthog 兼容性报错

### `config.py` — 配置与密钥管理

单例类 `Config`，统一管理所有配置项：

- **模型配置**：11 个云端模型 + 5 个本地模型的参数定义
- **路径配置**：向量库路径、文档路径、项目根目录
- **文档策略**：支持的文件扩展名、压缩包限制（成员数/解压大小）
- **API Key 加密持久化**：Fernet 加密存储到 `data/encrypted_keys.json`，启动自动加载解密
- **运行时配置持久化**：`data/runtime_config.json`，跨重启保留用户设置
- **背景预热**：可配置延迟启动、指定预热模型列表
- **占位值过滤**：`_PLACEHOLDER_PREFIX = "your-"`，`.env` 中 `your-*-api-key` 格式的占位值自动识别为未配置

### `src/auth.py` — 认证与加密

| 功能 | 说明 |
|------|------|
| `init_auth(password)` | 从密码派生 JWT 密钥和 Fernet 加密密钥（PBKDF2-HMAC-SHA256，100000 次迭代） |
| `verify_password(password)` | 验证登录密码，HMAC 常量时间比较防时序攻击 |
| `create_token()` | 生成 JWT Token（HS256，24h 有效期，含 jti 防重放） |
| `verify_token(token)` | 验证 JWT Token |
| `encrypt_api_key(plaintext)` | Fernet 对称加密 API Key |
| `decrypt_api_key(ciphertext)` | Fernet 解密 API Key |
| `mask_value(value, visible_start=4, visible_end=4)` | 脱敏显示，保留首尾各 N 位 |
| `require_auth(credentials)` | FastAPI 依赖注入，校验 JWT |

### `src/chat_history.py` — 会话管理

基于 JSON 文件的会话存储：

- `ChatHistoryManager` 单例类
- 会话数据目录：`data/chat_history/`
- 每个会话一个 `.json` 文件
- **UUID v4 校验**：`_validate_session_id()` 严格校验格式，防止路径遍历攻击
- **会话级锁**：每个 session_id 一把 `threading.Lock`，防止同一会话并发写入导致数据丢失
- **原子写入**：`_save_session()` 先写临时文件，再 `os.replace` 原子替换，防止崩溃时数据丢失
- **自动标题**：`auto_title_from_question()` 截取问题前 30 字符，在自然边界处截断
- **重新生成支持**：`replace_last_ai_message()` 替换最后一条 AI 消息

### `src/document_loader.py` — 文档加载器

- 按文件后缀自动选择对应 LangChain Loader
- Markdown 解析失败时回退为纯文本
- ZIP 压缩包解包递归处理
- 压缩包安全校验：路径遍历拦截、成员数限制（200）、解压大小限制（100MB）
- 过滤 `__MACOSX`、`.DS_Store`、`Thumbs.db` 等元数据文件
- source 元数据归一化为纯文件名
- 文档分块：`RecursiveCharacterTextSplitter`，参数从 Config 读取

支持格式：`.txt .md .markdown .pdf .docx .csv .json .html .htm .xml .yml .yaml .zip`

### `src/vector_store.py` — 向量库管理

- `VectorStoreManager` 单例类
- 延迟加载 Embedding 模型（`sentence-transformers/all-MiniLM-L6-v2`）
- Chroma 向量库创建/加载/清除/重建
- **文档快照与变更检测**：`get_documents_snapshot()` 计算每个文件的 name/size/mtime_ns/content_hash(SHA256)
- **增量构建**：仅有新增文档时增量追加，避免全量重建
- **全量重建备份/恢复**：构建前将旧库重命名为 `.bak`，构建成功后删除备份，失败则自动回滚
- **原子写入索引状态**：`_write_index_state()` 使用临时文件 + `os.replace`
- **删除文档同步清理**：`delete_document_from_vector_store()` 按 source 元数据匹配删除 chunks
- **Chroma 缓存清理**：`_reset_chroma_system_cache()` 清除进程级缓存
- 知识库三态判断：`exists` / `current` / `stale`

### `src/qa_engine.py` — 问答引擎

RAG 主链路编排：

```
用户问题 → 向量检索 → [Reranker 重排] → 提示词组装 → LLM 生成 → 答案
```

**运行时类**：

| 类 | 说明 |
|----|------|
| `OpenAICompatibleLLMRuntime` | 云端模型运行时（ChatOpenAI），支持 invoke 和 stream |
| `LocalLLMRuntime` | 本地模型运行时（transformers pipeline），temperature=0 时自动使用贪心解码（`do_sample=False`） |
| `WenxinLLMRuntime` | 文心一言运行时（OAuth 2.0 + SSE 流式），401/403 自动重试，支持多轮对话 |
| `QAEngine` | 问答引擎核心，向量检索 + 可选 Reranker 重排 + Prompt 拼装 |
| `RuntimeRegistry` | 运行时注册表（单例），LLM 缓存 + Reranker 缓存，并发模型加载使用 `threading.Event` 等待机制 |

**关键特性**：
- 流式输出：`stream_answer()` 通过生成器逐 token 输出，自动跳过 "答案：" 前缀
- 多轮对话：`_format_history()` 取最近 10 轮，过长消息截断至 500 字符
- 并发模型加载：使用 `threading.Event` 实现等待机制，避免同一模型被多个线程同时加载
- 加载超时：30 分钟

### `src/trace_logger.py` — 追踪日志

- Pipeline 级结构化日志：`trace_id`、`chain`、`stage`、`message`、`details`
- `new_trace_id(prefix)` 生成格式为 `{prefix}-{uuid_hex[:8]}` 的追踪 ID
- JSON 格式输出，独立 Logger 命名空间（`rag.pipeline`），`propagate=False`

## 数据流

### 文档构建链路

```
POST /api/documents/upload
  → 文件校验（后缀白名单/大小/路径安全）
  → DocumentLoader 读取
  → 文本分割（Chunk）
  → 保存到 documents/

POST /api/vectorstore/build
  → 扫描 documents/ 目录
  → 对比 _index_state.json 快照（SHA256 内容哈希）
  → 无变更 → 跳过构建
  → 仅有新增 → 增量追加
  → 有修改/删除 → 备份旧库 → 全量重建 → 成功删除备份 / 失败回滚
```

### 问答链路

```
POST /api/query
  → 检查知识库状态（stale → 拒绝）
  → 检查/创建会话 → 保存用户消息
  → VectorStore 相似度检索 → Top-K 文档
  → [Reranker 重排序 → Top-N 文档]
  → 构建 System Prompt + Context
  → LLM 生成答案
  → 保存 AI 回复
  → 返回答案 + 检索信息
```

### 流式问答链路

```
POST /api/query/stream
  → 同上检索流程
  → stream_answer() 生成器
  → SSE 事件流：token → data: {"chunk": "..."}\n\n
  → 流结束：data: {"done": true, "retrieval_info": [...], "rerank_info": [...]}\n\n
  → 保存完整回答到会话历史
```

## 运行时行为

### 模型预热
- `/api/preload` 触发指定模型加载到 RuntimeRegistry
- `/api/preload/status` 查询加载状态（idle/loading/ready/failed）
- 背景预热（`BACKGROUND_PRELOAD_ENABLED=true`）在启动延迟后自动加载
- 并发请求时，同一模型只加载一次，其他线程等待加载完成

### 构建并发保护
- `threading.Lock` 保证同一时刻只有一个构建任务
- 并发请求返回 409 Conflict
- `/api/vectorstore/build/status` 可查询当前构建状态

### 知识库状态机

```
                存在 & 快照一致 → current（可问答）
                ↑
上传新文档 → 快照变化 → stale（需重建，阻止问答）
                ↓
          构建 → 备份旧库 → 清除 & 重建 → current
                ↓ 失败
              回滚旧库
```

### 会话并发保护
- 每个 session_id 一把 `threading.Lock`
- 文件写入使用原子操作（临时文件 + `os.replace`）
- UUID v4 格式校验防止路径遍历

## 启动方式

### 安装依赖

```bash
cd backend
pip3 install -r requirements.txt
```

### 配置

```bash
cp .env.example .env
# 编辑 .env，至少配置 AUTH_PASSWORD
```

### 启动服务

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

### API 文档

启动后访问 `http://localhost:8000/docs`（Swagger UI）或 `http://localhost:8000/redoc`。

## CLI 工具

```bash
# 构建知识库
python cli.py build

# 查询问答
python cli.py query "什么是 RAG？"

# 查看可用模型
python cli.py models

# 交互式对话
python main.py
```

## 配置说明

### 密钥配置

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 |
| `QWEN_API_KEY` | 阿里通义千问 |
| `ZHIPU_API_KEY` | 智谱 AI |
| `KIMI_API_KEY` | 月之暗面 Kimi |
| `DEEPSEEK_API_KEY` | DeepSeek |
| `SILICONFLOW_API_KEY` | 硅基流动 |
| `GROQ_API_KEY` | Groq |
| `MISTRAL_API_KEY` | Mistral AI |
| `BAICHUAN_API_KEY` | 百川智能 |
| `STEPFUN_API_KEY` | 阶跃星辰 |
| `WENXIN_API_KEY` | 百度文心一言 |
| `WENXIN_SECRET_KEY` | 文心一言 Secret Key |

> 占位值（如 `your-openai-api-key`）会被自动识别为未配置。

### 系统配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AUTH_PASSWORD` | `admin` | 前端登录密码 |
| `DEFAULT_MODEL` | `qwen` | 默认模型 |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | 嵌入模型 |
| `RERANKER_MODEL` | `BAAI/bge-reranker-base` | 重排模型 |
| `CHUNK_SIZE` | `500` | 文档分块大小 |
| `CHUNK_OVERLAP` | `50` | 分块重叠 |
| `MAX_TOKENS` | `4096` | 最大生成长度 |
| `TEMPERATURE` | `0.1` | 生成温度 |
| `TOP_K` | `5` | 检索返回数量 |
| `RERANKER_TOP_N` | `3` | 重排序保留数 |
| `VECTOR_DB_PATH` | `data/chroma` | 向量库路径 |
| `DOCUMENTS_PATH` | `documents` | 文档存储路径 |
| `BACKGROUND_PRELOAD_ENABLED` | `true` | 启用后台预热 |
| `BACKGROUND_PRELOAD_MODELS` | `local-huge` | 后台预热模型列表（逗号分隔） |
| `BACKGROUND_PRELOAD_DELAY_SECONDS` | `15` | 预热延迟 |
| `BACKGROUND_PRELOAD_USE_RERANKER` | `false` | 预热是否加载 Reranker |
| `ARCHIVE_MAX_MEMBERS` | `200` | ZIP 最大文件数 |
| `ARCHIVE_MAX_UNCOMPRESSED_BYTES` | `104857600` | ZIP 最大解压大小（100MB） |
| `HF_ENDPOINT` | — | HuggingFace 镜像地址（国内建议 `https://hf-mirror.com`） |

## 注意事项

- `langchain-chroma==0.1.2` 与 `chromadb==0.5.5` 版本绑定，不可随意升级
- 首次启动会自动下载 Embedding 模型，约 90MB
- 本地 LLM 模型首次使用会自动从 Hugging Face 下载
- 大型本地模型（7B+）需要 16GB+ 内存，建议启用后台预热
- API Key 使用 Fernet 加密存储，密钥派生自 `AUTH_PASSWORD`
- 修改 `AUTH_PASSWORD` 后已加密的 API Key 将无法解密，需重新配置
- SSE 流式端点的认证通过 URL 参数 `?token=` 传递，WSGI 代理服务器需要透传查询参数
- 本地模型 `temperature=0` 时自动使用贪心解码（`do_sample=False`），避免 transformers 报错
- LangChain 遥测已在启动时禁用，避免 posthog 兼容性报错
