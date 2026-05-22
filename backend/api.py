import os

# 禁用 langchain 遥测，避免 posthog capture() 兼容性报错
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGCHAIN_TELEMETRY", "false")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")

import asyncio
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from config import Config
from src.document_loader import DocumentLoader
from src.vector_store import VectorStoreManager
from src.qa_engine import QAEngine, RuntimeRegistry
from src.trace_logger import log_pipeline, new_trace_id
from src.chat_history import ChatHistoryManager, _validate_session_id
from src.auth import init_auth, verify_password, create_token, require_auth, verify_token

app = FastAPI(title="知识库 RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 免认证路径
_PUBLIC_PATHS = {"/api/health", "/api/auth/login", "/docs", "/openapi.json", "/redoc"}


@app.middleware("http")
async def auth_middleware(request, call_next):
    """全局认证中间件：除公开路径外，所有请求需携带有效 JWT。
    支持 Authorization header 或 URL ?token= 参数（SSE 兼容）。"""
    if request.url.path in _PUBLIC_PATHS or request.url.path.startswith("/api/auth/"):
        return await call_next(request)
    # OPTIONS 预检请求放行
    if request.method == "OPTIONS":
        return await call_next(request)

    # 优先取 Authorization header，其次取 URL ?token 参数
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = request.query_params.get("token")

    if not token or not verify_token(token):
        return JSONResponse(
            status_code=401,
            content={"detail": "未登录，请先登录"},
        )
    return await call_next(request)

class QueryRequest(BaseModel):
    question: str
    model: str = Config.DEFAULT_MODEL
    temperature: float = Config.TEMPERATURE
    max_tokens: int = Config.MAX_TOKENS
    top_k: int = Config.TOP_K
    use_reranker: bool = False
    reranker_top_n: int = Config.RERANKER_TOP_N
    session_id: Optional[str] = None

class ModelConfigRequest(BaseModel):
    model: str
    api_key: Optional[str] = None

class SystemConfigRequest(BaseModel):
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    embedding_model: Optional[str] = None
    reranker_model: Optional[str] = None

class SessionTitleRequest(BaseModel):
    title: str

class CreateSessionRequest(BaseModel):
    title: Optional[str] = None


class PreloadRequest(BaseModel):
    model: str = Config.DEFAULT_MODEL
    use_reranker: bool = False


class LoginRequest(BaseModel):
    password: str


def get_documents_root():
    root_path = Path(Config.DOCUMENTS_PATH).resolve()
    root_path.mkdir(parents=True, exist_ok=True)
    return root_path


def validate_document_filename(filename: str):
    if not filename or not filename.strip():
        raise HTTPException(status_code=400, detail="文件名不能为空")

    candidate = filename.strip()
    safe_name = Path(candidate).name
    if safe_name != candidate or safe_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="文件名不合法")

    suffix = Path(safe_name).suffix.lower()
    if suffix not in Config.SUPPORTED_DOCUMENT_EXTENSIONS:
        allowed_types = ", ".join(sorted(Config.SUPPORTED_DOCUMENT_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"仅支持以下文件类型: {allowed_types}")

    return safe_name


def resolve_document_path(filename: str):
    documents_root = get_documents_root()
    safe_name = validate_document_filename(filename)
    file_path = (documents_root / safe_name).resolve()
    if file_path.parent != documents_root:
        raise HTTPException(status_code=400, detail="文件路径不合法")
    return safe_name, file_path


def get_runtime_registry():
    runtime_registry = getattr(app.state, "runtime_registry", None)
    if runtime_registry is None:
        runtime_registry = RuntimeRegistry()
        app.state.runtime_registry = runtime_registry
    return runtime_registry

# 构建并发锁，防止同时构建导致状态文件损坏
_build_lock = threading.Lock()
_build_in_progress = False


def preload_runtime(model, use_reranker):
    print(f"🔄 开始预热运行时，模型: {model}, 启用 Reranker: {use_reranker}")
    runtime_registry = get_runtime_registry()
    preload_result = runtime_registry.preload(
        model_name=model,
        use_reranker=use_reranker,
    )

    vector_store_loaded = False
    if os.path.exists(Config.VECTOR_DB_PATH):
        vector_store_manager = VectorStoreManager()
        vector_store_loaded = vector_store_manager.get_vector_store_status()["current"]

    return {
        "status": "success",
        "message": "Models preloaded successfully",
        "model": preload_result["model"],
        "used_reranker": use_reranker,
        "llm_runtime": preload_result["llm_runtime"],
        "reranker_model": preload_result["reranker_model"],
        "vector_store_loaded": vector_store_loaded,
    }


def _start_preload_background(model, use_reranker):
    runtime_registry = get_runtime_registry()
    status = runtime_registry.get_llm_status(model)

    if status["state"] == "ready":
        return {"status": "ready", "model": model, "cached": True}

    if status["state"] == "loading":
        return {"status": "loading", "model": model}

    def load_in_background():
        try:
            runtime_registry.preload(
                model_name=model,
                use_reranker=use_reranker,
            )
        except Exception as e:
            print(f"后台预加载失败 [{model}]: {e}")

    threading.Thread(
        target=load_in_background,
        name=f"preload-bg-{model}",
        daemon=True,
    ).start()

    return {"status": "started", "model": model}


def schedule_background_preload():
    if not Config.BACKGROUND_PRELOAD_ENABLED:
        return

    models_to_preload = tuple(
        model_name
        for model_name in Config.BACKGROUND_PRELOAD_MODELS
        if model_name in Config.MODEL_CONFIGS
    )
    if not models_to_preload:
        return

    def worker():
        delay_seconds = max(Config.BACKGROUND_PRELOAD_DELAY_SECONDS, 0)
        if delay_seconds:
            time.sleep(delay_seconds)

        runtime_registry = get_runtime_registry()
        for model_name in models_to_preload:
            trace_id = new_trace_id("bg-preload")
            log_pipeline(
                trace_id,
                "background_preload",
                "background_preload_start",
                "开始后台延迟预热本地模型",
                model=model_name,
                use_reranker=Config.BACKGROUND_PRELOAD_USE_RERANKER,
                delay_seconds=delay_seconds,
            )
            try:
                runtime_registry.preload(
                    model_name=model_name,
                    use_reranker=Config.BACKGROUND_PRELOAD_USE_RERANKER,
                )
                log_pipeline(
                    trace_id,
                    "background_preload",
                    "background_preload_complete",
                    "后台模型预热完成",
                    model=model_name,
                )
            except Exception as exc:
                log_pipeline(
                    trace_id,
                    "background_preload",
                    "background_preload_error",
                    "后台模型预热失败",
                    model=model_name,
                    error=str(exc),
                )

    threading.Thread(
        target=worker,
        name="rag-background-preload",
        daemon=True,
    ).start()


@app.on_event("startup")
async def startup_event():
    app.state.runtime_registry = RuntimeRegistry()
    # 初始化认证模块
    init_auth(Config.AUTH_PASSWORD)
    # 加载加密的 API Keys
    Config._load_encrypted_keys()
    schedule_background_preload()

# ---- 认证 API ----

# 登录速率限制：每 IP 在窗口期内最多允许 MAX_ATTEMPTS 次失败
_LOGIN_RATE_WINDOW = 300  # 5 分钟窗口
_LOGIN_MAX_ATTEMPTS = 5   # 窗口内最多 5 次失败
_login_failures: dict[str, list[float]] = defaultdict(list)
_login_lock = threading.Lock()


def _check_login_rate(client_ip: str) -> None:
    """检查登录速率，超限则抛出 429。"""
    now = time.time()
    with _login_lock:
        # 清理过期记录
        cutoff = now - _LOGIN_RATE_WINDOW
        _login_failures[client_ip] = [
            t for t in _login_failures[client_ip] if t > cutoff
        ]
        if len(_login_failures[client_ip]) >= _LOGIN_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail=f"登录尝试过于频繁，请 {_LOGIN_RATE_WINDOW // 60} 分钟后再试",
            )


def _record_login_failure(client_ip: str) -> None:
    """记录一次登录失败。"""
    now = time.time()
    with _login_lock:
        _login_failures[client_ip].append(now)


@app.post("/api/auth/login")
async def login(body: LoginRequest, req: Request):
    """使用密码登录，返回 JWT Token。"""
    client_ip = req.client.host if req.client else "unknown"
    _check_login_rate(client_ip)
    if verify_password(body.password):
        token = create_token()
        return {"token": token, "token_type": "bearer"}
    _record_login_failure(client_ip)
    raise HTTPException(status_code=401, detail="密码错误")

@app.get("/api/auth/verify")
async def verify_auth(_token: str = Depends(require_auth)):
    """验证当前 Token 是否有效。"""
    return {"status": "ok"}

# ---- 公开接口（无需认证）----

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "RAG 个人知识库 API"}

@app.get("/api/preload")
async def preload_models(
    model: str = Config.DEFAULT_MODEL,
    use_reranker: bool = False,
):
    return _start_preload_background(model=model, use_reranker=use_reranker)


@app.post("/api/preload")
async def preload_models_by_request(request: PreloadRequest):
    return _start_preload_background(
        model=request.model,
        use_reranker=request.use_reranker,
    )


@app.get("/api/preload/status")
async def preload_status(model: str = Config.DEFAULT_MODEL):
    status = get_runtime_registry().get_llm_status(model)
    return {
        "model": model,
        "state": status["state"],
        "cached": status["cached"],
        "error": status["error"],
    }

@app.get("/api/models")
async def get_models():
    cloud_models = []
    local_models = []
    for name, config in Config.MODEL_CONFIGS.items():
        model_info = {
            "name": name,
            "model": config.get("model", ""),
            "description": config.get("description", config.get("model", ""))
        }
        if name.startswith("local"):
            local_models.append(model_info)
        else:
            cloud_models.append(model_info)
    return {
        "cloud_models": cloud_models,
        "local_models": local_models
    }

@app.get("/api/config")
async def get_config():
    return {
        "default_model": Config.DEFAULT_MODEL,
        "temperature": Config.TEMPERATURE,
        "max_tokens": Config.MAX_TOKENS,
        "top_k": Config.TOP_K,
        "chunk_size": Config.CHUNK_SIZE,
        "chunk_overlap": Config.CHUNK_OVERLAP
    }


@app.get("/api/config/keys")
async def get_api_key_status():
    """返回各模型 API Key 的脱敏状态，不暴露明文。"""
    keys_status = {}
    for model_name, model_config in Config.MODEL_CONFIGS.items():
        if "api_key_env" not in model_config:
            continue
        masked = Config.get_model_api_key_masked(model_name)
        keys_status[model_name] = {
            "configured": bool(masked),
            "masked": masked,
        }
    return {"keys": keys_status}

@app.post("/api/config")
async def update_config(request: ModelConfigRequest):
    runtime_invalidated = False

    if request.api_key is not None:
        try:
            Config.set_model_api_key(request.model, request.api_key)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        runtime_invalidated = get_runtime_registry().invalidate_llm(request.model)

    return {
        "status": "success",
        "runtime_invalidated": runtime_invalidated,
    }

@app.get("/api/documents")
async def list_documents():
    documents_root = get_documents_root()
    files = []
    for filename in os.listdir(documents_root):
        filepath = documents_root / filename
        if filepath.is_file():
            files.append({
                "name": filename,
                "size": filepath.stat().st_size
            })
    return {"documents": files}

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    trace_id = new_trace_id("upload")
    log_pipeline(
        trace_id,
        "document_build",
        "upload_request_received",
        "收到文档上传请求",
        filename=file.filename,
    )
    safe_name, file_path = resolve_document_path(file.filename)
    log_pipeline(
        trace_id,
        "document_build",
        "upload_validation_complete",
        "上传文件校验通过",
        original_filename=file.filename,
        safe_filename=safe_name,
        target_path=str(file_path),
    )
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    log_pipeline(
        trace_id,
        "document_build",
        "upload_persist_complete",
        "上传文件已保存到文档目录",
        safe_filename=safe_name,
        size_bytes=len(content),
        target_path=str(file_path),
    )

    return {"status": "success", "filename": safe_name, "trace_id": trace_id}

@app.delete("/api/documents/{filename:path}")
async def delete_document(filename: str):
    _, file_path = resolve_document_path(filename)
    if file_path.exists():
        file_path.unlink()
        # 同步清理向量库中该文档的 chunks
        try:
            vector_store_manager = VectorStoreManager()
            vector_store_manager.delete_document_from_vector_store(filename)
        except Exception as exc:
            print(f"Warning: 清理向量库文档 chunks 失败 [{filename}]: {exc}")
        return {"status": "success", "filename": filename}
    raise HTTPException(status_code=404, detail="Document not found")

TEXT_PREVIEW_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".json", ".html", ".htm", ".xml", ".yml", ".yaml"}
MAX_PREVIEW_SIZE = 500 * 1024  # 500KB

@app.get("/api/documents/preview/{filename:path}")
async def preview_document(filename: str):
    """预览文档内容，支持文本类格式直接返回内容，其他格式返回类型标识。"""
    _, file_path = resolve_document_path(filename)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")

    suffix = file_path.suffix.lower()
    file_size = file_path.stat().st_size

    if suffix in TEXT_PREVIEW_EXTENSIONS:
        if file_size > MAX_PREVIEW_SIZE:
            raise HTTPException(status_code=413, detail=f"文件过大（{file_size} bytes），无法预览")
        content = file_path.read_text(encoding="utf-8", errors="replace")
        return {
            "filename": filename,
            "type": "text",
            "size": file_size,
            "content": content,
            "lines": content.count("\n") + 1,
        }

    return {
        "filename": filename,
        "type": suffix.lstrip("."),
        "size": file_size,
        "content": None,
        "message": f"不支持预览 {suffix} 格式，请下载到本地查看",
    }

@app.post("/api/vectorstore/build")
async def build_vectorstore():
    global _build_in_progress

    # 并发保护：如果已在构建中，拒绝重复请求
    if not _build_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="知识库构建正在进行中，请稍后再试",
        )

    trace_id = new_trace_id("build")
    try:
        _build_in_progress = True
        print("🔄 开始构建向量库...")
        log_pipeline(
            trace_id,
            "document_build",
            "build_request_received",
            "收到知识库构建请求，开始执行完整文档构建链路",
            documents_path=Config.DOCUMENTS_PATH,
            vector_db_path=Config.VECTOR_DB_PATH,
        )
        doc_loader = DocumentLoader(trace_id=trace_id, chain="document_build")
        vector_store_manager = VectorStoreManager()
        documents_root = get_documents_root()
        log_pipeline(
            trace_id,
            "document_build",
            "build_documents_root_ready",
            "文档目录已准备就绪",
            documents_root=str(documents_root),
        )
        
        documents = doc_loader.load_documents(str(documents_root))
        if not documents:
            load_errors = doc_loader.get_last_errors()
            if load_errors:
                raise HTTPException(
                    status_code=400,
                    detail=f"未能成功加载文档: {load_errors[0]}",
                )
            raise HTTPException(
                status_code=400,
                detail="文档目录为空，请先在文档管理页面上传文档后再构建知识库",
            )
        
        print(f"📄 加载了 {len(documents)} 个文档")
        split_docs = doc_loader.split_documents(documents)
        print(f"✂️ 分割成 {len(split_docs)} 个块")
        document_snapshot = vector_store_manager.get_documents_snapshot()
        log_pipeline(
            trace_id,
            "document_build",
            "snapshot_collect_complete",
            "文档快照收集完成，准备写入索引状态",
            documents_count=len(document_snapshot),
            snapshot=document_snapshot,
        )
        
        vector_store_manager.create_vector_store(
            split_docs,
            document_snapshot=document_snapshot,
            trace_id=trace_id,
            chain="document_build",
        )
        
        print("✅ 向量库构建完成")
        log_pipeline(
            trace_id,
            "document_build",
            "build_complete",
            "知识库构建链路执行完成",
            documents_count=len(documents),
            chunks_count=len(split_docs),
        )
        return {
            "status": "success",
            "documents_count": len(documents),
            "chunks_count": len(split_docs),
            "trace_id": trace_id,
        }
    except HTTPException:
        log_pipeline(
            trace_id,
            "document_build",
            "build_http_error",
            "知识库构建链路返回业务错误",
        )
        raise
    except Exception as e:
        print(f"❌ 构建向量库失败: {e}")
        log_pipeline(
            trace_id,
            "document_build",
            "build_exception",
            "知识库构建链路发生异常",
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"构建知识库失败: {str(e)}",
        )
    finally:
        _build_in_progress = False
        _build_lock.release()

@app.get("/api/vectorstore/build/status")
async def build_status():
    """查询构建是否在进行中。"""
    return {
        "building": _build_in_progress,
    }

@app.get("/api/vectorstore/status")
async def vectorstore_status():
    status = VectorStoreManager().get_vector_store_status()
    return {
        "exists": status["current"],
        "indexed": status["exists"],
        "stale": status["stale"],
        "documents_count": status["documents_count"],
    }

@app.post("/api/query")
async def query(request: QueryRequest):
    trace_id = new_trace_id("query")
    try:
        # 校验 session_id 格式，防止路径遍历
        if request.session_id:
            try:
                _validate_session_id(request.session_id)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        print(f"🔍 处理查询请求，模型: {request.model}, 启用 Reranker: {request.use_reranker}")
        log_pipeline(
            trace_id,
            "query",
            "query_request_received",
            "收到问答请求，开始执行完整问答链路",
            question=request.question,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_k=request.top_k,
            use_reranker=request.use_reranker,
            reranker_top_n=request.reranker_top_n,
        )
        runtime_registry = get_runtime_registry()
        vector_store_manager = VectorStoreManager()
        vector_store_status = vector_store_manager.get_vector_store_status()
        log_pipeline(
            trace_id,
            "query",
            "vector_store_status_check",
            "知识库状态检查完成",
            vector_store_status=vector_store_status,
        )

        if not vector_store_status["exists"]:
            raise HTTPException(status_code=400, detail="Vector store not initialized. Please build it first.")
        if not vector_store_status["current"]:
            raise HTTPException(status_code=400, detail="Vector store is out of date. Please rebuild it after document changes.")

        vector_store = vector_store_manager.load_vector_store(trace_id=trace_id, chain="query")
        
        if vector_store is None:
            raise HTTPException(status_code=400, detail="Vector store not initialized. Please build it first.")
        
        try:
            qa_engine = QAEngine(
                vector_store,
                model_name=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_k=request.top_k,
                use_reranker=request.use_reranker,
                reranker_top_n=request.reranker_top_n,
                runtime_registry=runtime_registry,
            )
            qa_engine.set_trace(trace_id, "query")
            print(f"🤖 正在使用 {request.model} 生成回答...")
            
            # 加载对话历史用于多轮对话
            chat_history = None
            if request.session_id:
                chat_manager = ChatHistoryManager()
                session = chat_manager.get_session(request.session_id)
                if session:
                    chat_history = [
                        {"role": msg.role, "content": msg.content}
                        for msg in session.messages
                    ]
            
            result = qa_engine.get_answer(request.question, chat_history=chat_history)
            answer = result["answer"]
            retrieval_info = result["retrieval_info"]
            rerank_info = result["rerank_info"]
            
            print(f"✅ 回答生成完成，长度: {len(answer)} 字符")
            log_pipeline(
                trace_id,
                "query",
                "query_complete",
                "问答链路执行完成",
                model=request.model,
                answer_characters=len(answer),
                retrieval_count=len(retrieval_info),
                used_reranker=request.use_reranker,
            )
            
            # 保存对话历史
            session_id = request.session_id
            if session_id:
                chat_manager = ChatHistoryManager()
                # 检测是否为重新生成：如果最后一条 user 消息与当前问题相同，则只替换 AI 回复
                if chat_manager.is_last_user_message(session_id, request.question):
                    chat_manager.replace_last_ai_message(
                        session_id, answer,
                        retrieval_info=retrieval_info,
                        rerank_info=rerank_info,
                    )
                else:
                    result = chat_manager.add_message(session_id, "user", request.question)
                    if result is None:
                        raise HTTPException(status_code=404, detail="会话不存在，消息未保存")
                    chat_manager.add_message(session_id, "ai", answer,
                                             retrieval_info=retrieval_info,
                                             rerank_info=rerank_info)
                    chat_manager.auto_title_from_question(session_id, request.question)
            
            return {
                "answer": answer,
                "model": request.model,
                "used_reranker": request.use_reranker,
                "trace_id": trace_id,
                "retrieval_info": retrieval_info,
                "rerank_info": rerank_info,
            }
        except ValueError as e:
            log_pipeline(
                trace_id,
                "query",
                "query_value_error",
                "问答链路返回模型配置错误",
                error=str(e),
            )
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        log_pipeline(
            trace_id,
            "query",
            "query_http_error",
            "问答链路返回业务错误",
        )
        raise
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        log_pipeline(
            trace_id,
            "query",
            "query_exception",
            "问答链路发生异常",
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


# ==================== 对话历史 API ====================

@app.post("/api/chat/sessions")
async def create_session(request: CreateSessionRequest):
    manager = ChatHistoryManager()
    session = manager.create_session(request.title)
    return {
        "session_id": session.session_id,
        "title": session.title,
        "created_at": session.created_at
    }

@app.get("/api/chat/sessions")
async def list_sessions():
    manager = ChatHistoryManager()
    sessions = manager.list_sessions()
    return {"sessions": sessions}

@app.get("/api/chat/sessions/{session_id}")
async def get_session(session_id: str):
    manager = ChatHistoryManager()
    try:
        session = manager.get_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session.session_id,
        "title": session.title,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp,
                "retrieval_info": getattr(msg, "retrieval_info", []) or [],
                "rerank_info": getattr(msg, "rerank_info", []) or [],
            }
            for msg in session.messages
        ]
    }

@app.put("/api/chat/sessions/{session_id}/title")
async def update_session_title(session_id: str, request: SessionTitleRequest):
    manager = ChatHistoryManager()
    try:
        success = manager.update_session_title(session_id, request.title)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success"}

@app.delete("/api/chat/sessions/{session_id}")
async def delete_session(session_id: str):
    manager = ChatHistoryManager()
    try:
        success = manager.delete_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success"}

@app.delete("/api/chat/sessions")
async def clear_all_sessions():
    manager = ChatHistoryManager()
    count = manager.clear_all_sessions()
    return {"status": "success", "deleted_count": count}

# ==================== 系统配置 API ====================

@app.get("/api/config/system")
async def get_system_config():
    return {
        "chunk_size": Config.CHUNK_SIZE,
        "chunk_overlap": Config.CHUNK_OVERLAP,
        "embedding_model": Config.EMBEDDING_MODEL,
        "reranker_model": Config.RERANKER_MODEL,
        "default_model": Config.DEFAULT_MODEL,
        "max_tokens": Config.MAX_TOKENS,
        "temperature": Config.TEMPERATURE,
        "top_k": Config.TOP_K,
        "reranker_top_n": Config.RERANKER_TOP_N,
        "supported_document_extensions": list(Config.SUPPORTED_DOCUMENT_EXTENSIONS),
        "vector_db_path": Config.VECTOR_DB_PATH,
        "documents_path": Config.DOCUMENTS_PATH
    }

@app.post("/api/config/system")
async def update_system_config(request: SystemConfigRequest):
    updated = []
    if request.chunk_size is not None:
        Config.CHUNK_SIZE = request.chunk_size
        updated.append("chunk_size")
    if request.chunk_overlap is not None:
        Config.CHUNK_OVERLAP = request.chunk_overlap
        updated.append("chunk_overlap")
    if request.embedding_model is not None:
        old_model = Config.EMBEDDING_MODEL
        Config.EMBEDDING_MODEL = request.embedding_model
        updated.append("embedding_model")
        # embedding 模型变更时，清除缓存并标记向量库失效
        if request.embedding_model != old_model:
            VectorStoreManager._embeddings = None
            # 标记向量库为 stale（删除索引状态文件，使 get_vector_store_status 返回 stale=True）
            vs_manager = VectorStoreManager()
            index_state_path = vs_manager._index_state_path()
            if index_state_path.exists():
                index_state_path.unlink()
    if request.reranker_model is not None:
        old_reranker = Config.RERANKER_MODEL
        Config.RERANKER_MODEL = request.reranker_model
        updated.append("reranker_model")
        # reranker 模型变更时，清除 reranker 缓存
        if request.reranker_model != old_reranker:
            runtime_registry = get_runtime_registry()
            runtime_registry._reranker_cache = {}

    Config.save_config()
    return {"status": "success", "updated": updated}


# ==================== 流式查询 API ====================

from fastapi.responses import StreamingResponse
import json

@app.get("/api/query/stream")
async def query_stream(
    question: str,
    model: str = Config.DEFAULT_MODEL,
    temperature: float = Config.TEMPERATURE,
    max_tokens: int = Config.MAX_TOKENS,
    top_k: int = Config.TOP_K,
    use_reranker: bool = False,
    reranker_top_n: int = Config.RERANKER_TOP_N,
    session_id: Optional[str] = None,
):
    # 校验 session_id 格式，防止路径遍历
    if session_id:
        try:
            _validate_session_id(session_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    trace_id = new_trace_id("query_stream")
    
    async def generate():
        try:
            print(f"🔍 处理流式查询请求，模型: {model}")

            runtime_registry = get_runtime_registry()
            vector_store_manager = VectorStoreManager()
            vector_store_status = vector_store_manager.get_vector_store_status()

            if not vector_store_status["exists"] or not vector_store_status["current"]:
                yield f"data: {json.dumps({'error': 'Vector store not ready'}, ensure_ascii=False)}\n\n"
                return

            vector_store = vector_store_manager.load_vector_store(trace_id=trace_id, chain="query_stream")
            if vector_store is None:
                yield f"data: {json.dumps({'error': 'Vector store not initialized'}, ensure_ascii=False)}\n\n"
                return

            qa_engine = QAEngine(
                vector_store,
                model_name=model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_k=top_k,
                use_reranker=use_reranker,
                reranker_top_n=reranker_top_n,
                runtime_registry=runtime_registry,
            )
            qa_engine.set_trace(trace_id, "query_stream")

            # 加载对话历史用于多轮对话
            chat_history = None
            if session_id:
                chat_manager = ChatHistoryManager()
                session = chat_manager.get_session(session_id)
                if session:
                    chat_history = [
                        {"role": msg.role, "content": msg.content}
                        for msg in session.messages
                    ]

            # 使用后台线程 + asyncio Queue 运行同步生成器，避免阻塞事件循环
            loop = asyncio.get_event_loop()
            chunk_queue: asyncio.Queue = asyncio.Queue()
            # 哨兵值，标记生成结束
            _SENTINEL = object()

            def run_sync_generator():
                try:
                    for chunk in qa_engine.stream_answer(question, chat_history=chat_history):
                        loop.call_soon_threadsafe(chunk_queue.put_nowait, chunk)
                except Exception as e:
                    loop.call_soon_threadsafe(chunk_queue.put_nowait, e)
                finally:
                    loop.call_soon_threadsafe(chunk_queue.put_nowait, _SENTINEL)

            thread = threading.Thread(target=run_sync_generator, daemon=True)
            thread.start()

            full_answer = ""

            while True:
                item = await chunk_queue.get()
                if item is _SENTINEL:
                    break
                if isinstance(item, Exception):
                    yield f"data: {json.dumps({'error': str(item)}, ensure_ascii=False)}\n\n"
                    break

                if isinstance(item, dict):
                    # 流式结束，发送最终结果
                    done_data = {
                        'done': True,
                        'answer': item['answer'],
                        'retrieval_info': item['retrieval_info'],
                        'rerank_info': item['rerank_info'],
                        'used_reranker': item['used_reranker'],
                        'trace_id': trace_id,
                    }
                    yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"

                    # 保存对话历史
                    if session_id:
                        chat_manager = ChatHistoryManager()
                        # 检测是否为重新生成：如果最后一条 user 消息与当前问题相同，则只替换 AI 回复
                        if chat_manager.is_last_user_message(session_id, question):
                            chat_manager.replace_last_ai_message(
                                session_id, item['answer'],
                                retrieval_info=item.get('retrieval_info', []),
                                rerank_info=item.get('rerank_info', []),
                            )
                        else:
                            result = chat_manager.add_message(session_id, "user", question)
                            if result is None:
                                yield f"data: {json.dumps({'error': '会话不存在，消息未保存'}, ensure_ascii=False)}\n\n"
                                return
                            chat_manager.add_message(session_id, "ai", item['answer'],
                                                     retrieval_info=item.get('retrieval_info', []),
                                                     rerank_info=item.get('rerank_info', []))
                            chat_manager.auto_title_from_question(session_id, question)
                else:
                    # 发送流式文本块
                    full_answer += item
                    chunk_data = {
                        'done': False,
                        'chunk': item,
                        'full_answer': full_answer,
                    }
                    yield f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/query/stream")
async def query_stream_post(request: QueryRequest):
    """POST 版本的流式查询，参数通过 request body 传递，避免 URL 过长。"""
    return await query_stream(
        question=request.question,
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        top_k=request.top_k,
        use_reranker=request.use_reranker,
        reranker_top_n=request.reranker_top_n,
        session_id=request.session_id,
    )

