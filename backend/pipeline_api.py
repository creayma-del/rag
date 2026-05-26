"""RAG 管道可视化模块：管道阶段定义、文档分块预览、向量库详情。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from pathlib import Path

from config import Config
from src.vector_store import VectorStoreManager
from src.document_loader import DocumentLoader

router = APIRouter(tags=["RAG 管道"])


# ---- RAG 管道阶段定义 ----

PIPELINE_STAGES = [
    {
        "order": 1,
        "name": "document_loading",
        "label": "Document Loader 文档加载与解析",
        "description": "读取原始文档（PDF/HTML/Word/Markdown 等），使用对应的 Loader 解析为纯文本 Document 对象列表，每个 Document 包含文本内容和元数据（source、page 等）。",
        "input": "原始文档文件（PDF/HTML/Word/Markdown/TXT/CSV 等）",
        "output": "纯文本 Document 对象列表（含 metadata）",
        "config_keys": ["SUPPORTED_DOCUMENT_EXTENSIONS"],
        "module": "src/document_loader.py",
    },
    {
        "order": 2,
        "name": "text_splitting",
        "label": "Text Splitter 文本分块",
        "description": "将长文档切分为固定大小的文本块（chunk），每个 chunk 保留部分重叠内容以保持语义连贯性。使用 RecursiveCharacterTextSplitter 按段落/句子边界智能分割。",
        "input": "纯文本 Document 对象列表",
        "output": "文本块列表（每个 chunk 含文本 + 元数据）",
        "config_keys": ["CHUNK_SIZE", "CHUNK_OVERLAP"],
        "module": "src/document_loader.py",
    },
    {
        "order": 3,
        "name": "embedding",
        "label": "Embedding Model 向量化",
        "description": "使用 Sentence-Transformer 模型将每个文本块转换为高维浮点向量（如 768 维），捕捉文本的语义信息。相同语义的文本在向量空间中距离更近。",
        "input": "文本块列表",
        "output": "向量表示（如 768 维浮点数组）",
        "config_keys": ["EMBEDDING_MODEL"],
        "module": "src/vector_store.py",
    },
    {
        "order": 4,
        "name": "vector_store",
        "label": "Vector Store 向量存储与索引",
        "description": "将文本块及其向量存入 ChromaDB 向量数据库，建立基于 cosine 相似度的索引。支持增量更新和全量重建。此阶段完成后离线索引阶段结束。",
        "input": "文本块 + 对应向量",
        "output": "持久化的向量索引（ChromaDB）",
        "config_keys": ["VECTOR_DB_PATH"],
        "module": "src/vector_store.py",
    },
    {
        "order": 5,
        "name": "query_encoding",
        "label": "Query Encoder 查询编码",
        "description": "用户输入问题后，使用与索引阶段相同的 Embedding 模型将问题转换为向量表示，使其与文档向量处于同一语义空间。",
        "input": "用户查询文本",
        "output": "查询向量（与文档向量同维度）",
        "config_keys": ["EMBEDDING_MODEL"],
        "module": "src/qa_engine.py",
    },
    {
        "order": 6,
        "name": "retrieval",
        "label": "Retriever 相似度检索",
        "description": "使用查询向量在向量库中进行 cosine 相似度检索，返回 Top-K 个最相关的文档片段。相似度越高，文档与查询越相关。",
        "input": "查询向量",
        "output": "Top-K 相关文档片段（含相似度分数）",
        "config_keys": ["TOP_K"],
        "module": "src/qa_engine.py",
    },
    {
        "order": 7,
        "name": "reranking",
        "label": "Reranker 重排序（可选）",
        "description": "使用 CrossEncoder 交叉编码器对检索结果进行精排。与 Bi-Encoder（Embedding）不同，CrossEncoder 同时编码查询和文档，能更精确地评估相关性，但计算成本更高。",
        "input": "Top-K 检索结果",
        "output": "重排序后的文档片段（更精确的相关性分数）",
        "config_keys": ["RERANKER_MODEL", "RERANKER_TOP_N"],
        "module": "src/qa_engine.py",
    },
    {
        "order": 8,
        "name": "prompt_building",
        "label": "Prompt Builder 提示构建",
        "description": "将检索到的文档片段作为上下文（Context），结合对话历史和用户问题，组装为结构化 Prompt 模板，指导 LLM 基于给定上下文回答问题。",
        "input": "检索/重排结果 + 对话历史 + 用户问题",
        "output": "结构化 Prompt",
        "config_keys": [],
        "module": "src/qa_engine.py",
    },
    {
        "order": 9,
        "name": "llm_generation",
        "label": "LLM 答案生成",
        "description": "将结构化 Prompt 发送给大语言模型（如 Qwen、DeepSeek、本地模型等），模型基于上下文生成最终答案。支持流式输出。",
        "input": "结构化 Prompt",
        "output": "最终答案",
        "config_keys": ["DEFAULT_MODEL", "TEMPERATURE", "MAX_TOKENS"],
        "module": "src/qa_engine.py",
    },
]


# ---- 路由 ----

@router.get("/api/pipeline/stages")
async def get_pipeline_stages():
    """获取 RAG 管道完整阶段定义，用于前端可视化。"""
    # 附加当前配置值
    stages_with_config = []
    for stage in PIPELINE_STAGES:
        stage_copy = dict(stage)
        current_config = {}
        for key in stage["config_keys"]:
            val = getattr(Config, key, None)
            if isinstance(val, (set, frozenset)):
                current_config[key] = list(val)
            else:
                current_config[key] = val
        stage_copy["current_config"] = current_config
        stages_with_config.append(stage_copy)
    return {"stages": stages_with_config}


@router.get("/api/pipeline/indexing/status")
async def get_indexing_pipeline_status():
    """获取离线索引阶段的状态（文档加载 → 分块 → 向量化 → 存储）。"""
    vector_store_manager = VectorStoreManager()
    status = vector_store_manager.get_vector_store_status()

    return {
        "vector_store": {
            "exists": status["exists"],
            "current": status["current"],
            "stale": status["stale"],
            "documents_count": status["indexed_documents_count"],
            "embedding_model": Config.EMBEDDING_MODEL,
            "embedding_dimension": VectorStoreManager._embedding_dimension,
            "distance_function": status.get("distance_function"),
            "chunk_size": Config.CHUNK_SIZE,
            "chunk_overlap": Config.CHUNK_OVERLAP,
            "chunk_strategy": Config.CHUNK_STRATEGY,
        },
    }


@router.get("/api/pipeline/chunks")
async def list_chunks(
    source: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """预览向量库中的文档分块（chunks），帮助理解文本如何被切分和向量化。

    source 参数支持顶层文档名过滤：对于 ZIP 文档，会匹配所有
    source 以 "filename::" 开头的 chunk。
    """
    vector_store_manager = VectorStoreManager()
    vector_store = vector_store_manager.load_vector_store()
    if vector_store is None:
        raise HTTPException(status_code=400, detail="向量库未构建，请先构建知识库")

    collection = vector_store._collection

    # 获取所有分块数据
    result = collection.get(include=["documents", "metadatas"])

    # 按 source 过滤：精确匹配或 ZIP 内文件前缀匹配
    if source and result and result.get("ids"):
        zip_prefix = source + "::"
        filtered_indices = []
        for i, meta in enumerate(result["metadatas"]):
            src = meta.get("source", "") if meta else ""
            if src == source or src.startswith(zip_prefix):
                filtered_indices.append(i)

        # 重建过滤后的结果
        filtered_ids = [result["ids"][i] for i in filtered_indices]
        filtered_docs = [result["documents"][i] for i in filtered_indices] if result.get("documents") else []
        filtered_metas = [result["metadatas"][i] for i in filtered_indices] if result.get("metadatas") else []
        result = {"ids": filtered_ids, "documents": filtered_docs, "metadatas": filtered_metas}

    count = len(result.get("ids", []))

    chunks = []
    if result and result.get("ids"):
        total = len(result["ids"])
        end = min(offset + limit, total)
        for i in range(offset, end):
            chunk = {
                "id": result["ids"][i],
                "content": result["documents"][i] if result.get("documents") else "",
                "metadata": result["metadatas"][i] if result.get("metadatas") else {},
                "content_length": len(result["documents"][i]) if result.get("documents") and result["documents"][i] else 0,
            }
            chunks.append(chunk)

    return {
        "total": count,
        "limit": limit,
        "offset": offset,
        "chunks": chunks,
    }


@router.get("/api/pipeline/chunks/{chunk_id}")
async def get_chunk_detail(chunk_id: str):
    """获取单个分块的详细信息，包括完整文本和元数据。"""
    vector_store_manager = VectorStoreManager()
    vector_store = vector_store_manager.load_vector_store()
    if vector_store is None:
        raise HTTPException(status_code=400, detail="向量库未构建")

    collection = vector_store._collection
    result = collection.get(ids=[chunk_id], include=["documents", "metadatas", "embeddings"])

    if not result or not result.get("ids") or not result["ids"]:
        raise HTTPException(status_code=404, detail="分块不存在")

    return {
        "id": result["ids"][0],
        "content": result["documents"][0] if result.get("documents") else "",
        "metadata": result["metadatas"][0] if result.get("metadatas") else {},
        "embedding_dimension": len(result["embeddings"][0]) if result.get("embeddings") and result["embeddings"][0] else None,
        "embedding_preview": result["embeddings"][0][:5] if result.get("embeddings") and result["embeddings"][0] else None,
    }


@router.get("/api/pipeline/sources")
async def list_sources():
    """获取向量库中所有文档来源列表及其分块数量。

    按顶层文档名分组：ZIP 内文件（source 格式为 archive.zip::inner_file）
    归入对应的 ZIP 文件名下，而非单独列出。
    """
    vector_store_manager = VectorStoreManager()
    vector_store = vector_store_manager.load_vector_store()
    if vector_store is None:
        raise HTTPException(status_code=400, detail="向量库未构建")

    collection = vector_store._collection
    result = collection.get(include=["metadatas"])

    source_counts = {}
    if result and result.get("metadatas"):
        for meta in result["metadatas"]:
            source = meta.get("source", "unknown") if meta else "unknown"
            # ZIP 内文件格式：archive.zip::inner_file，取 :: 前的文件名作为顶层文档
            top_level_name = source.split("::")[0] if "::" in source else source
            source_counts[top_level_name] = source_counts.get(top_level_name, 0) + 1

    sources = [
        {"name": name, "chunk_count": count}
        for name, count in sorted(source_counts.items())
    ]
    return {"sources": sources, "total_chunks": sum(source_counts.values())}


# ---- 文件类型标签映射 ----

_FILE_TYPE_LABELS = {
    ".pdf": "PDF 文档",
    ".docx": "Word 文档",
    ".md": "Markdown 文档",
    ".markdown": "Markdown 文档",
    ".txt": "纯文本",
    ".csv": "CSV 表格",
    ".json": "JSON 数据",
    ".html": "HTML 网页",
    ".htm": "HTML 网页",
    ".xml": "XML 数据",
    ".yml": "YAML 配置",
    ".yaml": "YAML 配置",
    ".zip": "ZIP 压缩包",
}


@router.get("/api/pipeline/ingestion/preview")
async def get_ingestion_preview():
    """返回离线索引阶段每个步骤的真实数据样本，用于前端可视化展示。"""
    ingestion_step_names = ["document_loading", "text_splitting", "embedding", "vector_store"]

    # 构建 step_info
    steps = []
    for stage in PIPELINE_STAGES:
        if stage["name"] not in ingestion_step_names:
            continue
        current_config = {}
        for key in stage["config_keys"]:
            val = getattr(Config, key, None)
            if isinstance(val, (set, frozenset)):
                current_config[key] = list(val)
            else:
                current_config[key] = val
        step_info = {
            "order": stage["order"],
            "name": stage["name"],
            "label": stage["label"],
            "description": stage["description"],
            "input_desc": stage["input"],
            "output_desc": stage["output"],
            "module": stage["module"],
            "config": current_config,
        }
        steps.append({"step_info": step_info, "sample": None})

    # ---- document_loading sample ----
    try:
        documents_path = Path(Config.DOCUMENTS_PATH)
        file_list = []
        if documents_path.exists():
            for file_path in sorted(documents_path.iterdir()):
                if file_path.is_file() and file_path.suffix.lower() in Config.SUPPORTED_DOCUMENT_EXTENSIONS:
                    ext = file_path.suffix.lower()
                    file_list.append({
                        "name": file_path.name,
                        "size": file_path.stat().st_size,
                        "extension": ext,
                        "type_label": _FILE_TYPE_LABELS.get(ext, "未知类型"),
                    })

        # 解析一个文档的文本预览（优先选择非 ZIP 文档）
        text_preview = None
        preview_file = None
        for f in file_list:
            if f["extension"] != ".zip":
                preview_file = f
                break
        if preview_file is None and file_list:
            preview_file = file_list[0]

        if preview_file and preview_file["extension"] != ".zip":
            try:
                loader_instance = DocumentLoader()
                loader = loader_instance._create_loader(str(documents_path / preview_file["name"]))
                docs = loader.load()
                if docs:
                    text_preview = docs[0].page_content[:2000]
            except Exception:
                # Markdown 等格式 Loader 可能失败，回退到纯文本读取
                try:
                    from langchain_community.document_loaders import TextLoader
                    fallback_loader = TextLoader(str(documents_path / preview_file["name"]), encoding="utf-8")
                    docs = fallback_loader.load()
                    if docs:
                        text_preview = docs[0].page_content[:2000]
                except Exception:
                    text_preview = None

        steps[0]["sample"] = {
            "files": file_list,
            "text_preview": text_preview,
            "supported_extensions": sorted(list(Config.SUPPORTED_DOCUMENT_EXTENSIONS)),
            "loader_mapping": {
                ".pdf": "PyMuPDFLoader（基于 PyMuPDF，支持表格/图片提取）",
                ".md": "UnstructuredMarkdownLoader → TextLoader fallback",
                ".markdown": "UnstructuredMarkdownLoader → TextLoader fallback",
                ".docx": "Docx2txtLoader（基于 python-docx）",
                ".html": "UnstructuredHTMLLoader（基于 lxml）",
                ".htm": "UnstructuredHTMLLoader（基于 lxml）",
                ".csv": "CSVLoader（逐行解析）",
                ".txt": "TextLoader（纯文本，UTF-8）",
                ".json": "JSONLoader（结构化解析）",
                ".yaml": "TextLoader（纯文本）",
                ".yml": "TextLoader（纯文本）",
                ".xml": "UnstructuredXMLLoader（结构化解析）",
                ".zip": "ZIP 内逐文件解析（自动识别内部文件类型）",
            },
            "process_steps": [
                "1. 扫描 documents/ 目录，识别文件类型",
                "2. 根据文件扩展名选择对应的 Loader",
                "3. Loader 读取文件内容，解析为纯文本",
                "4. 为每个文档附加 metadata（source、page 等）",
                "5. 输出 Document 对象列表（page_content + metadata）",
            ],
            "why_metadata": "metadata 中的 source 字段用于追踪答案来源，page 字段用于定位原文页码",
        }
    except Exception:
        steps[0]["sample"] = None

    # ---- 依赖向量库的 sample ----
    # 优先使用 load_vector_store，如果返回 None（因策略变更等）则直接用 Chroma 打开
    vector_store_manager = VectorStoreManager()
    vector_store = None
    collection = None
    try:
        vector_store = vector_store_manager.load_vector_store()
        if vector_store is not None:
            collection = vector_store._collection
    except Exception:
        pass

    # load_vector_store 可能因 needs_chunk_strategy_rebuild 等原因返回 None
    # 但向量库文件可能实际存在，直接用 Chroma 打开以获取预览数据
    if collection is None:
        try:
            from chromadb import Chroma as ChromaDB
            from src.vector_store import VectorStoreManager as _VSM
            if vector_store_manager.embeddings is None:
                vector_store_manager._load_embeddings()
            vector_store_manager._reset_chroma_system_cache()
            from langchain_chroma import Chroma
            direct_store = Chroma(
                persist_directory=Config.VECTOR_DB_PATH,
                embedding_function=vector_store_manager.embeddings,
                collection_metadata=_VSM._COSINE_METADATA,
            )
            collection = direct_store._collection
        except Exception:
            pass

    if collection is not None:
        # ---- 获取全量数据（供多个步骤共用，减少重复查询） ----
        all_data = None
        try:
            all_data = collection.get(include=["documents", "metadatas"])
        except Exception:
            pass

        # ---- text_splitting sample ----
        try:
            if all_data is not None and all_data.get("ids"):
                first_source = None
                source_chunks = []
                all_lengths = []
                source_set = set()
                for i, meta in enumerate(all_data["metadatas"]):
                    src = meta.get("source", "") if meta else ""
                    top_level = src.split("::")[0] if "::" in src else src
                    source_set.add(top_level)
                    content = all_data["documents"][i] if all_data.get("documents") is not None else ""
                    all_lengths.append(len(content))
                    if first_source is None:
                        first_source = src
                    if src == first_source and len(source_chunks) < 3:
                        source_chunks.append({
                            "id": all_data["ids"][i],
                            "content_preview": content[:300],
                            "content_length": len(content),
                            "metadata": meta if meta else {},
                        })
                # 长度分布统计
                length_stats = {}
                if all_lengths:
                    length_stats = {
                        "min": min(all_lengths),
                        "max": max(all_lengths),
                        "avg": round(sum(all_lengths) / len(all_lengths), 1),
                        "total": len(all_lengths),
                    }
                # 长度分布直方图（按区间统计）
                length_buckets = {}
                if all_lengths:
                    bucket_size = 200
                    for l in all_lengths:
                        bucket = (l // bucket_size) * bucket_size
                        label = f"{bucket}-{bucket + bucket_size}"
                        length_buckets[label] = length_buckets.get(label, 0) + 1
                    length_buckets = dict(sorted(length_buckets.items()))

                steps[1]["sample"] = {
                    "source": first_source,
                    "chunks": source_chunks,
                    "total_chunks": len(all_data["ids"]),
                    "total_sources": len(source_set),
                    "chunk_strategy": Config.CHUNK_STRATEGY,
                    "chunk_size": Config.CHUNK_SIZE,
                    "chunk_overlap": Config.CHUNK_OVERLAP,
                    "length_stats": length_stats,
                    "length_distribution": length_buckets,
                    "strategy_explanation": {
                        "semantic": "语义分块：基于语义相似度自动识别段落边界，保持语义完整性，chunk 大小不固定",
                        "recursive": "递归字符分块：按分隔符层级（段落→句子→字符）递归切分，chunk 大小接近固定值",
                    },
                    "process_steps": [
                        "1. 接收 Document 对象列表（来自 Document Loader）",
                        "2. 根据策略选择分块器（SemanticChunker / RecursiveCharacterTextSplitter）",
                        "3. 语义分块：计算相邻句子嵌入的相似度差异，在差异大的地方切分",
                        "4. 递归分块：按分隔符层级递归切分，保证不超过 chunk_size",
                        "5. 相邻 chunk 保留 chunk_overlap 字符的重叠，保持语义连贯",
                        "6. 每个 chunk 继承原文档的 metadata（source 等）",
                    ],
                    "why_overlap": f"Overlap={Config.CHUNK_OVERLAP}：相邻 chunk 保留 {Config.CHUNK_OVERLAP} 字符重叠，避免关键信息被切断在 chunk 边界",
                }
            else:
                steps[1]["sample"] = None
        except Exception:
            steps[1]["sample"] = None

        # ---- embedding sample ----
        try:
            if all_data is not None and all_data.get("ids"):
                first_id = all_data["ids"][0]
                first_text = all_data["documents"][0] if all_data.get("documents") is not None else ""
                # 通过 ID 精确获取该 chunk 的 embedding，避免 limit 参数兼容问题
                emb_result = collection.get(ids=[first_id], include=["embeddings"])
                embeddings = emb_result.get("embeddings") if emb_result is not None else None
                # 注意：ChromaDB 返回的 embeddings 是 numpy 数组，
                # 不能用 `if embeddings` 做布尔判断（会抛 ValueError），必须用 `is not None`
                if embeddings is not None and len(embeddings) > 0 and embeddings[0] is not None:
                    embedding = embeddings[0]
                    # 将 numpy 数组转为 Python list，确保 JSON 可序列化
                    embedding_list = embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)
                    emb_min = min(embedding_list)
                    emb_max = max(embedding_list)
                    emb_mean = sum(embedding_list) / len(embedding_list)
                    emb_norm = sum(v ** 2 for v in embedding_list) ** 0.5
                    steps[2]["sample"] = {
                        "chunk_id": first_id,
                        "chunk_text": first_text[:300] if first_text else "",
                        "embedding_preview": [round(v, 4) for v in embedding_list[:10]],
                        "embedding_dimension": len(embedding_list),
                        "model_name": Config.EMBEDDING_MODEL,
                        "embedding_stats": {
                            "min": round(emb_min, 4),
                            "max": round(emb_max, 4),
                            "mean": round(emb_mean, 4),
                            "norm": round(emb_norm, 4),
                        },
                        "process_steps": [
                            "1. 接收文本块（chunk）作为输入",
                            "2. 文本经过 Tokenizer 分词为 Token 序列",
                            "3. Token 序列输入 Transformer 编码器（多层自注意力 + FFN）",
                            "4. 取 [CLS] Token 或平均池化作为句子表示",
                            "5. 归一化后输出固定维度的浮点向量",
                            "6. 向量中每个维度编码了文本的某种语义特征",
                        ],
                        "why_embedding": "Embedding 将离散的文本转换为连续的向量空间，使语义相似的文本在向量空间中距离更近，从而支持相似度检索",
                        "what_is_dimension": f"维度={len(embedding_list)}：每个文本被编码为一个 {len(embedding_list)} 维浮点向量，维度越高表达能力越强，但计算和存储成本也越高",
                    }
                else:
                    steps[2]["sample"] = None
            else:
                steps[2]["sample"] = None
        except Exception:
            steps[2]["sample"] = None

        # ---- vector_store sample ----
        try:
            status = vector_store_manager.get_vector_store_status()
            total_chunks = len(all_data["ids"]) if all_data is not None and all_data.get("ids") else 0

            # 构建索引结构：按 source 分组展示，返回完整 chunk_ids
            index_structure = []
            if all_data is not None and all_data.get("ids") and all_data.get("metadatas") is not None:
                source_map = {}
                for i, meta in enumerate(all_data["metadatas"]):
                    src = meta.get("source", "unknown") if meta else "unknown"
                    top_level = src.split("::")[0] if "::" in src else src
                    if top_level not in source_map:
                        source_map[top_level] = []
                    source_map[top_level].append(all_data["ids"][i])

                for src_name, chunk_ids in sorted(source_map.items()):
                    index_structure.append({
                        "source": src_name,
                        "chunk_count": len(chunk_ids),
                        "chunk_ids": chunk_ids,
                    })

            steps[3]["sample"] = {
                "exists": status["exists"],
                "documents_count": status["indexed_documents_count"],
                "total_chunks": total_chunks,
                "embedding_model": Config.EMBEDDING_MODEL,
                "embedding_dimension": VectorStoreManager._embedding_dimension,
                "chunk_strategy": Config.CHUNK_STRATEGY,
                "chunk_size": Config.CHUNK_SIZE,
                "chunk_overlap": Config.CHUNK_OVERLAP,
                "distance_function": "cosine",
                "storage_path": Config.VECTOR_DB_PATH,
                "index_structure": index_structure,
                "process_steps": [
                    "1. 接收所有 chunk 的向量表示和元数据",
                    "2. 创建 ChromaDB Collection（指定 cosine 距离函数）",
                    "3. 批量写入向量数据（add: ids + embeddings + documents + metadatas）",
                    "4. ChromaDB 自动构建 HNSW 索引（近似最近邻搜索）",
                    "5. 持久化到磁盘（persist_directory），重启后可恢复",
                    "6. 记录索引快照（_index_state.json），用于增量更新检测",
                ],
                "what_is_hnsw": "HNSW（Hierarchical Navigable Small World）：分层可导航小世界图索引，在精度和速度之间取得平衡，查询时间复杂度 O(log N)",
                "why_cosine": "余弦距离衡量向量方向的相似性，不受向量长度影响，适合语义相似度计算",
            }
        except Exception:
            steps[3]["sample"] = None
    else:
        # 向量库未构建，依赖向量库的 sample 返回 null
        steps[1]["sample"] = None
        steps[2]["sample"] = None
        steps[3]["sample"] = None

    return {"steps": steps}


@router.get("/api/pipeline/query/preview")
async def get_query_preview():
    """返回在线查询阶段每个步骤的配置和示例数据，用于前端可视化展示。
    不执行实际查询，仅展示各阶段的配置、输入输出格式和模拟数据。
    """
    query_step_names = ["query_encoding", "retrieval", "reranking", "prompt_building", "llm_generation"]

    # 构建 step_info
    steps = []
    for stage in PIPELINE_STAGES:
        if stage["name"] not in query_step_names:
            continue
        current_config = {}
        for key in stage["config_keys"]:
            val = getattr(Config, key, None)
            if isinstance(val, (set, frozenset)):
                current_config[key] = list(val)
            else:
                current_config[key] = val
        step_info = {
            "order": stage["order"],
            "name": stage["name"],
            "label": stage["label"],
            "description": stage["description"],
            "input_desc": stage["input"],
            "output_desc": stage["output"],
            "module": stage["module"],
            "config": current_config,
        }
        steps.append({"step_info": step_info, "sample": None})

    # 检查向量库是否可用
    vector_store_manager = VectorStoreManager()
    collection = None
    try:
        vector_store = vector_store_manager.load_vector_store()
        if vector_store is not None:
            collection = vector_store._collection
    except Exception:
        pass

    if collection is None:
        try:
            if vector_store_manager.embeddings is None:
                vector_store_manager._load_embeddings()
            vector_store_manager._reset_chroma_system_cache()
            from langchain_chroma import Chroma
            direct_store = Chroma(
                persist_directory=Config.VECTOR_DB_PATH,
                embedding_function=vector_store_manager.embeddings,
                collection_metadata=VectorStoreManager._COSINE_METADATA,
            )
            collection = direct_store._collection
        except Exception:
            pass

    if collection is None:
        return {"steps": steps}

    # ---- Step 1: Query Encoder 查询编码 ----
    try:
        import time as _time
        sample_question = "什么是 RAG？"
        t0 = _time.time()
        query_vector = vector_store_manager.embeddings.embed_query(sample_question)
        encode_ms = round((_time.time() - t0) * 1000, 1)
        query_vector_list = query_vector.tolist() if hasattr(query_vector, 'tolist') else list(query_vector)
        qv_min = min(query_vector_list)
        qv_max = max(query_vector_list)
        qv_mean = sum(query_vector_list) / len(query_vector_list)
        qv_norm = sum(v ** 2 for v in query_vector_list) ** 0.5
        steps[0]["sample"] = {
            "sample_question": sample_question,
            "query_vector_preview": [round(v, 4) for v in query_vector_list[:10]],
            "query_vector_dimension": len(query_vector_list),
            "embedding_model": Config.EMBEDDING_MODEL,
            "encode_duration_ms": encode_ms,
            "vector_stats": {
                "min": round(qv_min, 4),
                "max": round(qv_max, 4),
                "mean": round(qv_mean, 4),
                "norm": round(qv_norm, 4),
            },
            "why_same_model": "查询和文档必须使用同一个 Embedding 模型，才能在同一语义空间中计算相似度",
            "process_steps": [
                "1. 用户输入问题文本",
                "2. 文本经过 Tokenizer 分词",
                "3. Token 序列输入 Transformer 编码器",
                "4. 取 [CLS] 或池化层输出作为句子向量",
                "5. 归一化后得到查询向量",
            ],
        }
    except Exception:
        steps[0]["sample"] = None

    # ---- Step 2: Retriever 相似度检索 ----
    try:
        if steps[0]["sample"] is not None:
            t0 = _time.time()
            results = collection.query(
                query_embeddings=[query_vector],
                n_results=min(Config.TOP_K, collection.count()),
                include=["documents", "metadatas", "distances"],
            )
            retrieval_ms = round((_time.time() - t0) * 1000, 1)
            retrieved = []
            if results and results.get("ids") and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    content = results["documents"][0][i] if results.get("documents") and results["documents"][0] else ""
                    metadata = results["metadatas"][0][i] if results.get("metadatas") and results["metadatas"][0] else {}
                    distance = results["distances"][0][i] if results.get("distances") and results["distances"][0] else 0.0
                    similarity = round(1.0 - float(distance), 4)
                    retrieved.append({
                        "index": i + 1,
                        "source": metadata.get("source", "unknown") if metadata else "unknown",
                        "similarity": similarity,
                        "distance": round(float(distance), 4),
                        "content_preview": content[:300] + "..." if len(content) > 300 else content,
                        "content_length": len(content),
                    })
            # 计算相似度分布
            similarities = [r["similarity"] for r in retrieved]
            steps[1]["sample"] = {
                "top_k": Config.TOP_K,
                "distance_function": "cosine",
                "retrieved_count": len(retrieved),
                "retrieval_duration_ms": retrieval_ms,
                "total_chunks_in_store": collection.count(),
                "results": retrieved,
                "similarity_stats": {
                    "max": max(similarities) if similarities else 0,
                    "min": min(similarities) if similarities else 0,
                    "avg": round(sum(similarities) / len(similarities), 4) if similarities else 0,
                },
                "how_cosine_works": "余弦相似度衡量两个向量方向的接近程度，值域 [-1, 1]，1 表示完全相同方向，0 表示无关，-1 表示相反",
                "why_top_k": f"Top-K={Config.TOP_K} 表示只取最相似的 {Config.TOP_K} 个片段，平衡召回率和精度",
            }
        else:
            steps[1]["sample"] = None
    except Exception:
        steps[1]["sample"] = None

    # ---- Step 3: Reranker 重排序 ----
    reranker_enabled = Config.USE_RERANKER
    reranker_available = False
    reranker_obj = None
    if reranker_enabled:
        try:
            from src.qa_engine import RuntimeRegistry
            registry = RuntimeRegistry()
            reranker_obj = registry.get_reranker(True)
            reranker_available = reranker_obj is not None
        except Exception:
            reranker_available = False

    reranker_sample = {
        "enabled": reranker_enabled and reranker_available,
        "model": Config.RERANKER_MODEL,
        "top_n": Config.RERANKER_TOP_N,
        "description": "CrossEncoder 同时编码查询和文档，更精确评估相关性，但计算成本更高",
        "input_example": "Top-K 检索结果（如上方 5 个文档片段）",
        "output_example": "重排序后的文档片段（如 Top-3 最相关片段）",
        "comparison": {
            "bi_encoder": {
                "name": "Bi-Encoder（Embedding 检索）",
                "how": "查询和文档分别独立编码为向量，再计算向量相似度",
                "speed": "极快（向量检索毫秒级）",
                "accuracy": "中等（独立编码无法捕捉细粒度交互）",
                "use_case": "从海量文档中快速召回候选集",
            },
            "cross_encoder": {
                "name": "Cross-Encoder（Reranker 重排）",
                "how": "将查询和每个文档拼接后一起输入模型，输出相关性分数",
                "speed": "较慢（每个文档对都要前向推理一次）",
                "accuracy": "高（能捕捉查询-文档的细粒度交互特征）",
                "use_case": "对少量候选结果精排，提升最终相关性",
            },
        },
        "when_to_use": "当检索结果不够精准（如 Top-K 中混入不相关文档）时，开启 Reranker 可显著提升答案质量",
    }

    # 如果 Reranker 可用且有检索结果，实际执行重排序
    if reranker_available and reranker_obj is not None and steps[1]["sample"] is not None:
        try:
            import time as _time2
            retrieval_results = steps[1]["sample"]["results"]
            if retrieval_results:
                # 构造查询-文档对
                pairs = [(sample_question, r["content_preview"]) for r in retrieval_results]
                t0 = _time2.time()
                scores = reranker_obj.predict(pairs)
                rerank_ms = round((_time2.time() - t0) * 1000, 1)
                # 按分数排序
                scored = list(zip(retrieval_results, scores.tolist() if hasattr(scores, 'tolist') else list(scores)))
                scored.sort(key=lambda x: x[1], reverse=True)

                # 重排序前的排名（原始检索顺序）
                before = [
                    {"rank": r["index"], "source": r["source"], "similarity": r["similarity"]}
                    for r in retrieval_results
                ]
                # 重排序后的排名
                after = [
                    {
                        "new_rank": idx + 1,
                        "old_rank": r["index"],
                        "source": r["source"],
                        "reranker_score": round(float(score), 4),
                        "similarity": r["similarity"],
                        "rank_change": r["index"] - (idx + 1),  # 正数=上升，负数=下降
                    }
                    for idx, (r, score) in enumerate(scored[:Config.RERANKER_TOP_N])
                ]
                reranker_sample["rerank_results"] = {
                    "before": before,
                    "after": after,
                    "rerank_duration_ms": rerank_ms,
                    "input_count": len(retrieval_results),
                    "output_count": min(Config.RERANKER_TOP_N, len(retrieval_results)),
                }
        except Exception:
            pass

    steps[2]["sample"] = reranker_sample

    # ---- Step 4: Prompt Builder 提示构建 ----
    try:
        prompt_template = (
            "基于上下文和对话历史回答问题。\n"
            "{history}"
            "上下文：\n{context}\n\n"
            "问题：{question}\n"
            "答案："
        )
        # 用实际检索结果拼装完整 Prompt
        sample_context_parts = []
        if steps[1]["sample"] is not None:
            for r in steps[1]["sample"]["results"][:3]:
                sample_context_parts.append(r["content_preview"])
        sample_context = "\n\n---\n\n".join(sample_context_parts) if sample_context_parts else "（检索到的文档片段将拼接在此处...）"
        sample_history = ""
        sample_prompt = prompt_template.format(
            context=sample_context,
            question="什么是 RAG？",
            history=sample_history,
        )
        steps[3]["sample"] = {
            "prompt_template": prompt_template,
            "template_variables": [
                {"name": "{context}", "desc": "检索到的文档片段，用 \\n\\n 分隔拼接", "source": "Retriever / Reranker 输出"},
                {"name": "{history}", "desc": "对话历史（用户和 AI 的多轮对话记录）", "source": "ChatHistoryManager"},
                {"name": "{question}", "desc": "用户当前提出的问题", "source": "用户输入"},
            ],
            "prompt_preview": sample_prompt[:800],
            "prompt_full_length": len(sample_prompt),
            "context_documents": Config.TOP_K,
            "context_characters": len(sample_context),
            "has_history": False,
            "why_prompt_engineering": "好的 Prompt 能引导 LLM 基于给定上下文回答，减少幻觉，提高答案准确性",
        }
    except Exception:
        steps[3]["sample"] = None

    # ---- Step 5: LLM 答案生成 ----
    try:
        model_config = Config.MODEL_CONFIGS.get(Config.DEFAULT_MODEL, {})
        is_local = Config.DEFAULT_MODEL.startswith("local")
        hf_model = model_config.get("model", "") if is_local else ""
        api_base = model_config.get("api_base", "") if not is_local else ""
        api_model = model_config.get("model", "") if not is_local else ""
        description = model_config.get("description", "")
        steps[4]["sample"] = {
            "model": Config.DEFAULT_MODEL,
            "model_display": model_config.get("display_name", Config.DEFAULT_MODEL),
            "model_type": "local" if is_local else "cloud",
            "temperature": Config.TEMPERATURE,
            "max_tokens": Config.MAX_TOKENS,
            "runtime_class": model_config.get("runtime", "unknown"),
            "description": description,
            "hf_model": hf_model,
            "api_base": api_base,
            "api_model": api_model,
            "supports_streaming": True,
            "generation_process": [
                "1. 接收完整 Prompt 文本",
                "2. Tokenizer 将文本转为 Token ID 序列",
                "3. 模型逐 Token 自回归生成（每次预测下一个 Token）",
                "4. 流式输出：每生成一个 Token 立即返回给前端",
                "5. 遇到结束符或达到 Max Tokens 时停止",
            ],
            "what_is_temperature": f"Temperature={Config.TEMPERATURE}：控制生成随机性，越低越确定（0=贪心），越高越多样",
            "what_is_max_tokens": f"Max Tokens={Config.MAX_TOKENS}：限制生成答案的最大 Token 数，防止回答过长",
            "all_available_models": [
                {"key": k, "name": v.get("description", k), "type": "local" if k.startswith("local") else "cloud"}
                for k, v in Config.MODEL_CONFIGS.items()
            ],
        }
    except Exception:
        steps[4]["sample"] = None

    return {"steps": steps}
