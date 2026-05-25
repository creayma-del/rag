"""向量库管理模块：构建、状态查询。"""

import threading

from fastapi import APIRouter, HTTPException

from config import Config
from src.document_loader import DocumentLoader
from src.vector_store import VectorStoreManager
from src.trace_logger import new_trace_id, log_pipeline
from documents_api import get_documents_root

router = APIRouter(prefix="/api/vectorstore", tags=["向量库管理"])

# 构建并发锁，防止同时构建导致状态文件损坏
_build_lock = threading.Lock()
_build_in_progress = False


@router.post("/build")
async def build_vectorstore():
    """构建向量库。"""
    global _build_in_progress

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


@router.get("/build/status")
async def build_status():
    """查询构建是否在进行中。"""
    return {
        "building": _build_in_progress,
    }


@router.get("/status")
async def vectorstore_status():
    """查询向量库状态。"""
    status = VectorStoreManager().get_vector_store_status()
    return {
        "exists": status["current"],
        "indexed": status["exists"],
        "stale": status["stale"],
        "documents_count": status["documents_count"],
        "distance_function": status.get("distance_function"),
        "needs_distance_migration": status.get("needs_distance_migration", False),
        "embedding_dimension": status.get("embedding_dimension"),
    }
