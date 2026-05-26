import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from chromadb.api.client import SharedSystemClient
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from config import Config
from src.trace_logger import log_pipeline

class VectorStoreManager:
    _instance = None
    _embeddings = None
    _embedding_dimension = None
    _COSINE_METADATA = {"hnsw:space": "cosine"}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.vector_store = None
        self.embeddings = None
        self._initialized = True
    
    def _load_embeddings(self, trace_id=None, chain="document_build"):
        if VectorStoreManager._embeddings is None:
            print(f"📥 正在加载 Embeddings 模型: {Config.EMBEDDING_MODEL}")
            if trace_id:
                log_pipeline(
                    trace_id,
                    chain,
                    "embedding_load_start",
                    "开始加载 Embeddings 模型",
                    embedding_model=Config.EMBEDDING_MODEL,
                )
            VectorStoreManager._embeddings = HuggingFaceEmbeddings(
                model_name=Config.EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"}
            )
            # 计算向量维度：嵌入一段测试文本，取结果向量长度
            _test_vector = VectorStoreManager._embeddings.embed_query("dimension_probe")
            VectorStoreManager._embedding_dimension = len(_test_vector)
            print(f"✅ Embeddings 模型加载完成，向量维度: {VectorStoreManager._embedding_dimension}")
            if trace_id:
                log_pipeline(
                    trace_id,
                    chain,
                    "embedding_load_complete",
                    "Embeddings 模型加载完成",
                    embedding_model=Config.EMBEDDING_MODEL,
                    embedding_dimension=VectorStoreManager._embedding_dimension,
                )
        self.embeddings = VectorStoreManager._embeddings

    def get_embedding_dimension(self):
        """获取当前 Embedding 模型的向量维度。"""
        if VectorStoreManager._embedding_dimension is not None:
            return VectorStoreManager._embedding_dimension
        if self.embeddings is None:
            self._load_embeddings()
        # 兜底：模型已加载但维度未计算（热更新场景）
        if VectorStoreManager._embedding_dimension is None and self.embeddings is not None:
            _test_vector = self.embeddings.embed_query("dimension_probe")
            VectorStoreManager._embedding_dimension = len(_test_vector)
        return VectorStoreManager._embedding_dimension

    def _vector_store_root(self):
        return Path(Config.VECTOR_DB_PATH)

    def _index_state_path(self):
        return self._vector_store_root() / Config.INDEX_STATE_FILENAME

    def _reset_chroma_system_cache(self):
        # Chroma keeps a process-level shared client cache. After deleting the
        # persist directory, that cache can still point to an invalid tenant/db.
        try:
            SharedSystemClient.clear_system_cache()
        except Exception as exc:
            print(f"Warning: failed to clear Chroma system cache: {exc}")

    def _list_document_files(self):
        documents_root = Path(Config.DOCUMENTS_PATH)
        if not documents_root.exists():
            return []

        return sorted(
            file_path for file_path in documents_root.iterdir()
            if file_path.is_file() and file_path.suffix.lower() in Config.SUPPORTED_DOCUMENT_EXTENSIONS
        )

    def _compute_file_hash(self, file_path):
        """计算文件内容的 SHA256 哈希，用于检测内容变更。"""
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        return sha.hexdigest()

    def get_documents_snapshot(self):
        snapshot = []
        for file_path in self._list_document_files():
            file_stat = file_path.stat()
            snapshot.append({
                "name": file_path.name,
                "size": file_stat.st_size,
                "mtime_ns": file_stat.st_mtime_ns,
                "content_hash": self._compute_file_hash(file_path),
            })
        return snapshot

    def _find_diff(self, old_snapshot, new_snapshot):
        """对比新旧快照，返回增量/变更/删除的文档列表。"""
        old_by_name = {d["name"]: d for d in old_snapshot} if old_snapshot else {}
        new_by_name = {d["name"]: d for d in new_snapshot}

        added = []
        modified = []
        unchanged = []
        deleted = []

        for name, info in new_by_name.items():
            if name not in old_by_name:
                added.append(name)
            elif info.get("content_hash") != old_by_name[name].get("content_hash"):
                modified.append(name)
            else:
                unchanged.append(name)

        for name in old_by_name:
            if name not in new_by_name:
                deleted.append(name)

        return {
            "added": added,
            "modified": modified,
            "unchanged": unchanged,
            "deleted": deleted,
        }

    def _write_index_state(self, document_snapshot):
        state_path = self._index_state_path()
        state_path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps({
            "distance_function": "cosine",
            "embedding_model": Config.EMBEDDING_MODEL,
            "chunk_strategy": Config.CHUNK_STRATEGY,
            "documents": document_snapshot,
        }, ensure_ascii=False, indent=2)
        # 原子写入：先写临时文件，再 rename，防止崩溃时数据丢失
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=state_path.parent, suffix='.tmp', prefix='.index_state_'
        )
        try:
            with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                f.write(content)
            os.replace(tmp_path, state_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _read_index_state(self):
        state_path = self._index_state_path()
        if not state_path.exists():
            return None

        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
            # 兼容旧格式：纯列表（无 distance_function 字段）视为 L2
            if isinstance(data, list):
                return {"distance_function": "l2", "documents": data}
            return data
        except json.JSONDecodeError:
            return None

    def clear_vector_store(self, trace_id=None, chain="document_build"):
        vector_store_root = self._vector_store_root()
        self.vector_store = None
        if trace_id:
            log_pipeline(
                trace_id,
                chain,
                "vector_store_clear_start",
                "开始清理旧向量库目录",
                vector_db_path=str(vector_store_root),
                existed=vector_store_root.exists(),
            )
        self._reset_chroma_system_cache()
        if vector_store_root.exists():
            shutil.rmtree(vector_store_root)
        vector_store_root.mkdir(parents=True, exist_ok=True)
        if trace_id:
            log_pipeline(
                trace_id,
                chain,
                "vector_store_clear_complete",
                "旧向量库目录清理完成",
                vector_db_path=str(vector_store_root),
            )

    def get_vector_store_status(self):
        vector_store_root = self._vector_store_root()
        state = self._read_index_state()
        has_index_files = vector_store_root.exists() and any(
            child.name != Config.INDEX_STATE_FILENAME for child in vector_store_root.iterdir()
        )
        current_snapshot = self.get_documents_snapshot()
        indexed_snapshot = state.get("documents") if state else None
        # 仅比较 content_hash，忽略 mtime_ns 等不影响内容的元数据
        # 与 _find_diff 的逻辑保持一致
        indexed_hashes = {d["name"]: d.get("content_hash") for d in (indexed_snapshot or [])}
        current_hashes = {d["name"]: d.get("content_hash") for d in current_snapshot}
        is_current = has_index_files and indexed_hashes == current_hashes

        # 检测距离函数兼容性：旧索引使用 L2，当前版本要求 cosine
        distance_function = state.get("distance_function", "l2") if state else None
        needs_distance_migration = has_index_files and distance_function != "cosine"

        # 检测 Embedding 模型变化：模型不同则向量维度/语义空间不同，必须重建
        # 旧索引无 embedding_model 字段，视为需要重建
        indexed_embedding_model = state.get("embedding_model") if state else None
        needs_embedding_rebuild = (
            has_index_files
            and indexed_embedding_model != Config.EMBEDDING_MODEL
        )

        # 检测分块策略变化：策略不同则分块结果不同，需要重建
        indexed_chunk_strategy = state.get("chunk_strategy") if state else None
        needs_chunk_strategy_rebuild = (
            has_index_files
            and indexed_chunk_strategy != Config.CHUNK_STRATEGY
        )

        # 统计向量库中实际的唯一文档来源数（ZIP 内文件归为顶层文档）
        indexed_documents_count = 0
        if has_index_files:
            try:
                if self.embeddings is None:
                    self._load_embeddings()
                self._reset_chroma_system_cache()
                store = Chroma(
                    persist_directory=Config.VECTOR_DB_PATH,
                    embedding_function=self.embeddings,
                    collection_metadata=self._COSINE_METADATA,
                )
                all_meta = store._collection.get(include=["metadatas"])
                if all_meta and all_meta.get("metadatas"):
                    top_level_names = set()
                    for meta in all_meta["metadatas"]:
                        src = meta.get("source", "") if meta else ""
                        if src:
                            # ZIP 内文件格式：archive.zip::inner_file，取 :: 前的文件名
                            top_level_name = src.split("::")[0] if "::" in src else src
                            top_level_names.add(top_level_name)
                    indexed_documents_count = len(top_level_names)
            except Exception:
                pass

        return {
            "exists": has_index_files,
            "current": is_current and not needs_distance_migration and not needs_embedding_rebuild and not needs_chunk_strategy_rebuild,
            "stale": has_index_files and (not is_current or needs_distance_migration or needs_embedding_rebuild or needs_chunk_strategy_rebuild),
            "documents_count": len(current_snapshot),
            "indexed_documents_count": indexed_documents_count,
            "distance_function": distance_function,
            "needs_distance_migration": needs_distance_migration,
            "needs_embedding_rebuild": needs_embedding_rebuild,
            "needs_chunk_strategy_rebuild": needs_chunk_strategy_rebuild,
            "embedding_dimension": VectorStoreManager._embedding_dimension,
        }
    
    def create_vector_store(self, documents, document_snapshot=None, trace_id=None, chain="document_build"):
        if self.embeddings is None:
            self._load_embeddings(trace_id=trace_id, chain=chain)

        snapshot = document_snapshot or self.get_documents_snapshot()
        old_state = self._read_index_state()
        old_snapshot = old_state.get("documents") if old_state else None
        diff = self._find_diff(old_snapshot, snapshot)

        has_deletions = bool(diff["deleted"])
        has_modifications = bool(diff["modified"])
        has_additions = bool(diff["added"])
        can_incremental = not has_deletions and not has_modifications

        # 检测 Embedding 模型变化：模型不同则必须全量重建
        # 旧索引无 embedding_model 字段，视为需要重建
        indexed_embedding_model = old_state.get("embedding_model") if old_state else None
        if indexed_embedding_model != Config.EMBEDDING_MODEL:
            print(f"🔄 Embedding 模型变更（{indexed_embedding_model} → {Config.EMBEDDING_MODEL}），执行全量重建")
            if trace_id:
                log_pipeline(
                    trace_id,
                    chain,
                    "vector_store_embedding_model_changed",
                    "Embedding 模型变更，需要全量重建",
                    old_model=indexed_embedding_model,
                    new_model=Config.EMBEDDING_MODEL,
                )
            has_deletions = True  # 强制走全量重建路径
            can_incremental = False

        # 检测分块策略变化：策略不同则分块结果不同，需要全量重建
        indexed_chunk_strategy = old_state.get("chunk_strategy") if old_state else None
        if indexed_chunk_strategy != Config.CHUNK_STRATEGY:
            print(f"🔄 分块策略变更（{indexed_chunk_strategy} → {Config.CHUNK_STRATEGY}），执行全量重建")
            if trace_id:
                log_pipeline(
                    trace_id,
                    chain,
                    "vector_store_chunk_strategy_changed",
                    "分块策略变更，需要全量重建",
                    old_strategy=indexed_chunk_strategy,
                    new_strategy=Config.CHUNK_STRATEGY,
                )
            has_deletions = True
            can_incremental = False

        if trace_id:
            log_pipeline(
                trace_id,
                chain,
                "vector_store_diff",
                "文档差异分析完成",
                diff=diff,
                can_incremental=can_incremental,
            )

        # 如果只有新增且已有向量库，增量追加
        if can_incremental and has_additions and self._vector_store_root().exists():
            print(f"🔄 增量模式：仅处理 {len(diff['added'])} 个新增文档")
            if trace_id:
                log_pipeline(
                    trace_id,
                    chain,
                    "vector_store_incremental_add",
                    "增量模式：追加新增文档",
                    added_count=len(diff["added"]),
                    unchanged_count=len(diff["unchanged"]),
                )
            new_only_docs = self._filter_documents_by_names(documents, diff["added"])
            if new_only_docs:
                self._reset_chroma_system_cache()
                existing_store = Chroma(
                    persist_directory=Config.VECTOR_DB_PATH,
                    embedding_function=self.embeddings,
                    collection_metadata=self._COSINE_METADATA,
                )
                existing_store.add_documents(new_only_docs)
            self._write_index_state(snapshot)
            if trace_id:
                log_pipeline(
                    trace_id,
                    chain,
                    "vector_store_incremental_complete",
                    "增量追加完成",
                    added_docs=len(new_only_docs) if new_only_docs else 0,
                )
            return  # 增量完成，无需全量重建

        # 无任何变更且向量库已存在，跳过重建
        # 但需检查向量库中是否有残留的旧文档 chunk（source 不在快照中）
        if not has_deletions and not has_modifications and not has_additions:
            if self._vector_store_root().exists():
                if self._has_stale_chunks(snapshot):
                    print("⚠️ 检测到向量库中存在残留的旧文档 chunks，执行全量重建")
                    if trace_id:
                        log_pipeline(
                            trace_id,
                            chain,
                            "vector_store_stale_chunks_detected",
                            "向量库中存在残留的旧文档 chunks，需要全量重建",
                        )
                    # 强制走全量重建路径：标记为有删除
                    has_deletions = True
                else:
                    print("✅ 文档无变更，跳过知识库重建")
                    if trace_id:
                        log_pipeline(
                            trace_id,
                            chain,
                            "vector_store_skip",
                            "文档无变更，跳过重建",
                            unchanged_count=len(diff["unchanged"]),
                        )
                    return

        # 有删除或修改，全量重建
        if has_deletions or has_modifications:
            print(f"🔄 检测到文档变更（删除:{len(diff['deleted'])} 修改:{len(diff['modified'])}），执行全量重建")
            if trace_id:
                log_pipeline(
                    trace_id,
                    chain,
                    "vector_store_full_rebuild",
                    "文档有删除或修改，执行全量重建",
                    deleted=diff["deleted"],
                    modified=diff["modified"],
                )

        # 全量重建或首次构建
        # 先备份旧库，新库构建成功后删除备份；失败则恢复旧库
        vector_store_root = self._vector_store_root()
        backup_dir = None
        if vector_store_root.exists() and any(vector_store_root.iterdir()):
            backup_dir = vector_store_root.with_name(vector_store_root.name + ".bak")
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            os.rename(vector_store_root, backup_dir)
            vector_store_root.mkdir(parents=True, exist_ok=True)
            if trace_id:
                log_pipeline(
                    trace_id,
                    chain,
                    "vector_store_backup_created",
                    "旧向量库已备份，开始创建新库",
                    backup_path=str(backup_dir),
                )
        else:
            self.clear_vector_store(trace_id=trace_id, chain=chain)

        if trace_id:
            log_pipeline(
                trace_id,
                chain,
                "vector_store_create_start",
                "开始创建 Chroma 向量库",
                documents=len(documents),
                vector_db_path=Config.VECTOR_DB_PATH,
            )

        try:
            self._reset_chroma_system_cache()
            self.vector_store = Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings,
                persist_directory=Config.VECTOR_DB_PATH,
                collection_metadata=self._COSINE_METADATA,
            )
            self._write_index_state(snapshot)
            # 新库构建成功，删除备份
            if backup_dir and backup_dir.exists():
                shutil.rmtree(backup_dir)
            if trace_id:
                log_pipeline(
                    trace_id,
                    chain,
                    "vector_store_create_complete",
                    "Chroma 向量库创建完成",
                    documents=len(documents),
                    snapshot_documents=len(snapshot),
                    vector_db_path=Config.VECTOR_DB_PATH,
                )
        except Exception:
            # 新库构建失败，恢复旧库
            if backup_dir and backup_dir.exists():
                print("⚠️ 新向量库构建失败，正在恢复旧库...")
                self.vector_store = None
                self._reset_chroma_system_cache()
                if vector_store_root.exists():
                    shutil.rmtree(vector_store_root)
                os.rename(backup_dir, vector_store_root)
                if trace_id:
                    log_pipeline(
                        trace_id,
                        chain,
                        "vector_store_rollback",
                        "新库构建失败，已恢复旧向量库",
                        backup_path=str(backup_dir),
                    )
            raise

        return self.vector_store

    def _has_stale_chunks(self, current_snapshot):
        """检查向量库中是否存在不在当前快照中的旧文档 chunks。

        比较向量库中所有 chunk 的 source 元数据与快照中的文档名，
        如果有不匹配的 source（包括 ZIP 内文件格式的 source），
        说明有残留的旧数据需要全量重建清理。
        """
        try:
            if self.embeddings is None:
                self._load_embeddings()
            self._reset_chroma_system_cache()
            store = Chroma(
                persist_directory=Config.VECTOR_DB_PATH,
                embedding_function=self.embeddings,
                collection_metadata=self._COSINE_METADATA,
            )
            all_meta = store._collection.get(include=["metadatas"])
            if not all_meta or not all_meta.get("metadatas"):
                return False

            # 构建当前快照中的文档名集合
            snapshot_names = {d["name"] for d in current_snapshot} if current_snapshot else set()

            for meta in all_meta["metadatas"]:
                src = meta.get("source", "") if meta else ""
                if not src:
                    continue
                # ZIP 内文件格式：archive.zip::inner_file，取 :: 前的文件名
                top_level_name = src.split("::")[0] if "::" in src else src
                if top_level_name not in snapshot_names:
                    return True
            return False
        except Exception:
            return False

    def _filter_documents_by_names(self, documents, names):
        """从文档列表中筛选属于指定文件名的 chunk。"""
        name_set = set(names)
        return [
            doc for doc in documents
            if Path(doc.metadata.get("source", "")).name in name_set
        ]
    
    def delete_document_from_vector_store(self, filename, trace_id=None, chain="document_build"):
        """从向量库中删除指定文档的所有 chunk（按 source 元数据匹配）。
        删除后自动更新索引状态（移除该文档的快照记录）。"""
        status = self.get_vector_store_status()
        if not status["exists"]:
            return False

        if self.embeddings is None:
            self._load_embeddings(trace_id=trace_id, chain=chain)

        self._reset_chroma_system_cache()
        store = Chroma(
            persist_directory=Config.VECTOR_DB_PATH,
            embedding_function=self.embeddings,
            collection_metadata=self._COSINE_METADATA,
        )

        if trace_id:
            log_pipeline(
                trace_id,
                chain,
                "vector_store_delete_document_start",
                "开始从向量库中删除文档 chunks",
                filename=filename,
            )

        # ChromaDB collection.delete 按 metadata filter 删除
        # 兼容 source 为纯文件名、完整路径、ZIP 内文件 (archive.zip::file) 的情况
        import os
        source_patterns = [filename]
        # 完整路径兼容（历史数据）
        alt_source = os.path.join(Config.DOCUMENTS_PATH, filename)
        source_patterns.append(alt_source)
        # ZIP 内文件兼容：source 格式为 "archive.zip::inner_file"
        zip_prefix = filename + "::"

        try:
            for pattern in source_patterns:
                result = store._collection.get(where={"source": pattern})
                if result and result.get("ids"):
                    store._collection.delete(where={"source": pattern})

            # 查找所有以 "filename::" 开头的 ZIP 内文件 source
            all_meta = store._collection.get(include=["metadatas"])
            if all_meta and all_meta.get("metadatas"):
                zip_ids = []
                for i, meta in enumerate(all_meta["metadatas"]):
                    src = meta.get("source", "") if meta else ""
                    if src.startswith(zip_prefix):
                        zip_ids.append(all_meta["ids"][i])
                if zip_ids:
                    store._collection.delete(ids=zip_ids)
        except Exception as exc:
            print(f"Warning: 删除文档 chunks 失败 [{filename}]: {exc}")
            if trace_id:
                log_pipeline(
                    trace_id,
                    chain,
                    "vector_store_delete_document_error",
                    "从向量库删除文档 chunks 失败",
                    filename=filename,
                    error=str(exc),
                )
            return False

        # 更新索引状态：从快照中移除该文档
        state = self._read_index_state()
        if state and "documents" in state:
            state["documents"] = [
                doc for doc in state["documents"]
                if doc.get("name") != filename
            ]
            self._write_index_state(state["documents"])

        if trace_id:
            log_pipeline(
                trace_id,
                chain,
                "vector_store_delete_document_complete",
                "文档 chunks 已从向量库中删除",
                filename=filename,
            )
        return True

    def load_vector_store(self, trace_id=None, chain="query"):
        if self.embeddings is None:
            self._load_embeddings(trace_id=trace_id, chain=chain)
        status = self.get_vector_store_status()
        if trace_id:
            log_pipeline(
                trace_id,
                chain,
                "vector_store_load_check",
                "检查向量库加载条件",
                status=status,
                vector_db_path=Config.VECTOR_DB_PATH,
            )
        # Embedding 模型变更时旧向量库不兼容，不能加载
        if status.get("needs_embedding_rebuild"):
            if trace_id:
                log_pipeline(
                    trace_id,
                    chain,
                    "vector_store_load_skip_embedding_mismatch",
                    "Embedding 模型已变更，旧向量库不兼容，需重建",
                    old_model=status.get("embedding_model"),
                    new_model=Config.EMBEDDING_MODEL,
                )
            return None
        # 分块策略变更时需重建，不能加载旧向量库
        if status.get("needs_chunk_strategy_rebuild"):
            if trace_id:
                log_pipeline(
                    trace_id,
                    chain,
                    "vector_store_load_skip_chunk_strategy_mismatch",
                    "分块策略已变更，需重建",
                    old_strategy=status.get("chunk_strategy"),
                    new_strategy=Config.CHUNK_STRATEGY,
                )
            return None
        if status["exists"]:
            self._reset_chroma_system_cache()
            self.vector_store = Chroma(
                persist_directory=Config.VECTOR_DB_PATH,
                embedding_function=self.embeddings,
                collection_metadata=self._COSINE_METADATA,
            )
            if trace_id:
                log_pipeline(
                    trace_id,
                    chain,
                    "vector_store_load_complete",
                    "向量库加载完成",
                    vector_db_path=Config.VECTOR_DB_PATH,
                )
        return self.vector_store
