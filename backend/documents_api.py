"""文档管理模块：上传、删除、列表、预览。"""

import os
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

from config import Config
from src.vector_store import VectorStoreManager
from src.trace_logger import new_trace_id, log_pipeline

router = APIRouter(prefix="/api/documents", tags=["文档管理"])

TEXT_PREVIEW_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".json", ".html", ".htm", ".xml", ".yml", ".yaml"}
MAX_PREVIEW_SIZE = 500 * 1024  # 500KB


# ---- 文档操作工具函数 ----

def get_documents_root() -> Path:
    root_path = Path(Config.DOCUMENTS_PATH).resolve()
    root_path.mkdir(parents=True, exist_ok=True)
    return root_path


def validate_document_filename(filename: str) -> str:
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


def resolve_document_path(filename: str) -> tuple[str, Path]:
    documents_root = get_documents_root()
    safe_name = validate_document_filename(filename)
    file_path = (documents_root / safe_name).resolve()
    if file_path.parent != documents_root:
        raise HTTPException(status_code=400, detail="文件路径不合法")
    return safe_name, file_path


# ---- 路由 ----

@router.get("")
async def list_documents():
    """获取文档列表。"""
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


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """上传文档。"""
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
    try:
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
    except Exception:
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                pass
        raise
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


@router.delete("/{filename:path}")
async def delete_document(filename: str):
    """删除文档。"""
    _, file_path = resolve_document_path(filename)
    if file_path.exists():
        file_path.unlink()
        vector_cleanup_warning = None
        try:
            vector_store_manager = VectorStoreManager()
            vector_store_manager.delete_document_from_vector_store(filename)
        except Exception as exc:
            vector_cleanup_warning = f"向量库清理失败: {exc}"
            print(f"Warning: 清理向量库文档 chunks 失败 [{filename}]: {exc}")
        result: dict = {"status": "success", "filename": filename}
        if vector_cleanup_warning:
            result["warning"] = vector_cleanup_warning
        return result
    raise HTTPException(status_code=404, detail="Document not found")


@router.get("/preview/{filename:path}")
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
