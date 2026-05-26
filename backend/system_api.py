"""系统配置模块：健康检查、基础配置、系统配置管理。"""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from config import Config
from src.vector_store import VectorStoreManager
from src.qa_engine import RuntimeRegistry
from dependencies import get_runtime_registry

router = APIRouter(tags=["系统管理"])


# ---- 请求模型 ----

class SystemConfigRequest(BaseModel):
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    chunk_strategy: Optional[str] = None
    semantic_breakpoint_type: Optional[str] = None
    semantic_breakpoint_amount: Optional[float] = None
    semantic_min_chunk_size: Optional[int] = None
    embedding_model: Optional[str] = None
    reranker_model: Optional[str] = None
    use_reranker: Optional[bool] = None


# ---- 路由 ----

@router.get("/api/health")
async def health_check():
    """健康检查。"""
    return {"status": "ok", "service": "RAG 个人知识库 API"}


@router.get("/api/config")
async def get_config():
    """获取基础配置。"""
    return {
        "default_model": Config.DEFAULT_MODEL,
        "temperature": Config.TEMPERATURE,
        "max_tokens": Config.MAX_TOKENS,
        "top_k": Config.TOP_K,
        "chunk_size": Config.CHUNK_SIZE,
        "chunk_overlap": Config.CHUNK_OVERLAP,
        "chunk_strategy": Config.CHUNK_STRATEGY,
    }


@router.get("/api/config/system")
async def get_system_config():
    """获取系统配置。"""
    return {
        "chunk_size": Config.CHUNK_SIZE,
        "chunk_overlap": Config.CHUNK_OVERLAP,
        "chunk_strategy": Config.CHUNK_STRATEGY,
        "semantic_breakpoint_type": Config.SEMANTIC_BREAKPOINT_TYPE,
        "semantic_breakpoint_amount": Config.SEMANTIC_BREAKPOINT_AMOUNT,
        "semantic_min_chunk_size": Config.SEMANTIC_MIN_CHUNK_SIZE,
        "embedding_model": Config.EMBEDDING_MODEL,
        "embedding_dimension": VectorStoreManager._embedding_dimension,
        "reranker_model": Config.RERANKER_MODEL,
        "use_reranker": Config.USE_RERANKER,
        "default_model": Config.DEFAULT_MODEL,
        "max_tokens": Config.MAX_TOKENS,
        "temperature": Config.TEMPERATURE,
        "top_k": Config.TOP_K,
        "reranker_top_n": Config.RERANKER_TOP_N,
        "supported_document_extensions": list(Config.SUPPORTED_DOCUMENT_EXTENSIONS),
        "vector_db_path": Config.VECTOR_DB_PATH,
        "documents_path": Config.DOCUMENTS_PATH
    }


@router.post("/api/config/system")
async def update_system_config(
    request: SystemConfigRequest,
    runtime_registry: RuntimeRegistry = Depends(get_runtime_registry),
):
    """更新系统配置。"""
    updated = []
    if request.chunk_size is not None:
        Config.CHUNK_SIZE = request.chunk_size
        updated.append("chunk_size")
    if request.chunk_overlap is not None:
        Config.CHUNK_OVERLAP = request.chunk_overlap
        updated.append("chunk_overlap")
    if request.chunk_strategy is not None:
        old_strategy = Config.CHUNK_STRATEGY
        Config.CHUNK_STRATEGY = request.chunk_strategy
        updated.append("chunk_strategy")
        if request.chunk_strategy != old_strategy:
            vs_manager = VectorStoreManager()
            index_state_path = vs_manager._index_state_path()
            if index_state_path.exists():
                index_state_path.unlink()
    if request.semantic_breakpoint_type is not None:
        Config.SEMANTIC_BREAKPOINT_TYPE = request.semantic_breakpoint_type
        updated.append("semantic_breakpoint_type")
    if request.semantic_breakpoint_amount is not None:
        Config.SEMANTIC_BREAKPOINT_AMOUNT = request.semantic_breakpoint_amount
        updated.append("semantic_breakpoint_amount")
    if request.semantic_min_chunk_size is not None:
        Config.SEMANTIC_MIN_CHUNK_SIZE = request.semantic_min_chunk_size
        updated.append("semantic_min_chunk_size")
    if request.embedding_model is not None:
        old_model = Config.EMBEDDING_MODEL
        Config.EMBEDDING_MODEL = request.embedding_model
        updated.append("embedding_model")
        if request.embedding_model != old_model:
            VectorStoreManager._embeddings = None
            VectorStoreManager._embedding_dimension = None
            vs_manager = VectorStoreManager()
            index_state_path = vs_manager._index_state_path()
            if index_state_path.exists():
                index_state_path.unlink()
    if request.reranker_model is not None:
        old_reranker = Config.RERANKER_MODEL
        Config.RERANKER_MODEL = request.reranker_model
        updated.append("reranker_model")
        if request.reranker_model != old_reranker:
            runtime_registry._reranker_cache = {}
    if request.use_reranker is not None:
        Config.USE_RERANKER = request.use_reranker
        updated.append("use_reranker")

    Config.save_config()
    return {"status": "success", "updated": updated}
