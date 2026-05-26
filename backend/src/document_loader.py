import os
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from langchain_community.document_loaders import (
    TextLoader,
    PyMuPDFLoader,
    Docx2txtLoader,
    UnstructuredMarkdownLoader,
    UnstructuredFileLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from config import Config
from src.trace_logger import log_pipeline


class DocumentLoader:
    def __init__(self, trace_id=None, chain="document_build", embeddings=None):
        self.last_errors = []
        self.trace_id = trace_id
        self.chain = chain
        self.embeddings = embeddings
        self.chunk_strategy = Config.CHUNK_STRATEGY

        # 递归字符分块器（fallback 或用户选择）
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.CHUNK_SIZE,
            chunk_overlap=Config.CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", ". ", "! ", "? ", "; ", ", ", " ", ""],
        )

        # 语义分块器（需要 embeddings 模型）
        self.semantic_splitter = None
        if self.chunk_strategy == "semantic" and embeddings is not None:
            self.semantic_splitter = SemanticChunker(
                embeddings=embeddings,
                breakpoint_threshold_type=Config.SEMANTIC_BREAKPOINT_TYPE,
                breakpoint_threshold_amount=Config.SEMANTIC_BREAKPOINT_AMOUNT,
                min_chunk_size=Config.SEMANTIC_MIN_CHUNK_SIZE,
                sentence_split_regex=r"(?<=[。！？；\.\!\?;])\s*",
            )

    def _log(self, stage, message, **details):
        if self.trace_id:
            log_pipeline(self.trace_id, self.chain, stage, message, **details)



    def _is_supported_document(self, file_path, include_archives=True):
        suffix = Path(file_path).suffix.lower()
        if suffix not in Config.SUPPORTED_DOCUMENT_EXTENSIONS:
            return False
        if not include_archives and suffix in Config.ARCHIVE_SUPPORTED_EXTENSIONS:
            return False
        return True

    def _create_loader(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()

        if ext in {".txt", ".markdown", ".csv", ".json", ".html", ".htm", ".xml", ".yml", ".yaml"}:
            return TextLoader(file_path, encoding="utf-8")
        if ext == ".pdf":
            return PyMuPDFLoader(file_path)
        if ext == ".docx":
            return Docx2txtLoader(file_path)
        if ext == ".md":
            return UnstructuredMarkdownLoader(file_path)
        return UnstructuredFileLoader(file_path)

    def _is_archive_metadata_member(self, member_path):
        parts = member_path.parts
        filename = member_path.name

        if "__MACOSX" in parts:
            return True
        if filename.startswith("._"):
            return True
        if filename in {".DS_Store", "Thumbs.db"}:
            return True
        return False

    def _validate_archive_member(self, member):
        member_path = PurePosixPath(member.filename)
        if member.is_dir():
            return None
        if member_path.is_absolute() or ".." in member_path.parts:
            raise ValueError(f"压缩包包含非法路径: {member.filename}")
        if self._is_archive_metadata_member(member_path):
            return None
        if not self._is_supported_document(member.filename, include_archives=False):
            return None
        return member_path

    def _load_zip_file(self, file_path):
        documents = []
        total_uncompressed_bytes = 0

        self._log("archive_open", "开始解析 ZIP 压缩包", archive=file_path)
        with zipfile.ZipFile(file_path) as archive:
            members = archive.infolist()
            self._log(
                "archive_scan",
                "压缩包扫描完成",
                archive=file_path,
                member_count=len(members),
            )
            if len(members) > Config.ARCHIVE_MAX_MEMBERS:
                raise ValueError(
                    f"压缩包文件数过多，最多支持 {Config.ARCHIVE_MAX_MEMBERS} 个文件"
                )

            with tempfile.TemporaryDirectory(prefix="rag-archive-") as temp_dir:
                temp_root = Path(temp_dir)
                resolved_temp_root = temp_root.resolve()
                for member in members:
                    member_path = self._validate_archive_member(member)
                    if member_path is None:
                        self._log(
                            "archive_member_skip",
                            "跳过压缩包内不支持的文件",
                            archive=file_path,
                            member=member.filename,
                        )
                        continue

                    total_uncompressed_bytes += member.file_size
                    if total_uncompressed_bytes > Config.ARCHIVE_MAX_UNCOMPRESSED_BYTES:
                        raise ValueError(
                            "压缩包解压后的总大小超出限制，请拆分后重新上传"
                        )

                    extracted_path = (temp_root / member_path).resolve()
                    if resolved_temp_root not in extracted_path.parents and extracted_path != resolved_temp_root:
                        raise ValueError(f"压缩包包含越界路径: {member.filename}")

                    extracted_path.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, open(extracted_path, "wb") as target:
                        target.write(source.read())

                    self._log(
                        "archive_member_extract",
                        "压缩包文件解压完成，准备读取",
                        archive=file_path,
                        member=member.filename,
                        extracted_path=str(extracted_path),
                        size_bytes=member.file_size,
                    )
                    docs = self._load_single_file(str(extracted_path))
                    archive_source = f"{Path(file_path).name}::{member_path.as_posix()}"
                    for doc in docs:
                        metadata = dict(doc.metadata or {})
                        metadata["source"] = archive_source
                        metadata["archive"] = Path(file_path).name
                        doc.metadata = metadata
                    documents.extend(docs)

        self._log(
            "archive_complete",
            "ZIP 压缩包解析完成",
            archive=file_path,
            loaded_documents=len(documents),
            total_uncompressed_bytes=total_uncompressed_bytes,
        )

        return documents

    def _load_single_file(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        if ext in Config.ARCHIVE_SUPPORTED_EXTENSIONS:
            return self._load_zip_file(file_path)

        loader = self._create_loader(file_path)
        self._log(
            "document_load_start",
            "开始读取单个文档",
            file=file_path,
            extension=ext,
            loader=loader.__class__.__name__,
        )
        try:
            docs = loader.load()
            # 将 source 元数据归一化为纯文件名，确保与向量库快照的 name 字段一致
            for doc in docs:
                if "source" in (doc.metadata or {}):
                    doc.metadata["source"] = Path(doc.metadata["source"]).name
            self._log(
                "document_load_complete",
                "单个文档读取完成",
                file=file_path,
                extension=ext,
                loaded_documents=len(docs),
            )
            return docs
        except Exception as exc:
            if ext == ".md":
                # Markdown uses a plain-text fallback to avoid unstructured parser/environment issues.
                fallback_loader = TextLoader(file_path, encoding="utf-8")
                self._log(
                    "document_load_fallback",
                    "Markdown Loader 失败，回退到纯文本读取",
                    file=file_path,
                    extension=ext,
                    error=str(exc),
                    fallback_loader=fallback_loader.__class__.__name__,
                )
                docs = fallback_loader.load()
                # 将 source 元数据归一化为纯文件名
                for doc in docs:
                    if "source" in (doc.metadata or {}):
                        doc.metadata["source"] = Path(doc.metadata["source"]).name
                self._log(
                    "document_load_complete",
                    "Markdown 回退读取完成",
                    file=file_path,
                    extension=ext,
                    loaded_documents=len(docs),
                )
                return docs
            self._log(
                "document_load_error",
                "单个文档读取失败",
                file=file_path,
                extension=ext,
                error=str(exc),
            )
            raise exc
    
    def load_documents(self, path):
        self.last_errors = []
        documents = []
        self._log("document_scan_start", "开始扫描文档输入源", path=path)

        if os.path.isfile(path):
            try:
                documents = self._load_single_file(path)
            except Exception as exc:
                self.last_errors.append(f"{path}: {exc}")
        elif os.path.isdir(path):
            root = Path(path)
            supported_files = sorted(
                file_path for file_path in root.rglob("*")
                if file_path.is_file() and self._is_supported_document(file_path)
            )
            self._log(
                "document_scan_complete",
                "目录扫描完成",
                path=path,
                supported_file_count=len(supported_files),
                files=[str(file_path) for file_path in supported_files],
            )

            for file_path in supported_files:
                try:
                    docs = self._load_single_file(str(file_path))
                    documents.extend(docs)
                except Exception as exc:
                    error_message = f"{file_path}: {exc}"
                    self.last_errors.append(error_message)
                    print(f"Error loading file {error_message}")

        self._log(
            "document_scan_summary",
            "文档扫描与读取结束",
            path=path,
            loaded_documents=len(documents),
            error_count=len(self.last_errors),
            errors=self.last_errors,
        )
        return documents

    def get_last_errors(self):
        return list(self.last_errors)
    
    def split_documents(self, documents):
        self._log(
            "document_split_start",
            "开始切分文档",
            input_documents=len(documents),
            chunk_strategy=self.chunk_strategy,
            chunk_size=Config.CHUNK_SIZE,
            chunk_overlap=Config.CHUNK_OVERLAP,
        )

        if self.chunk_strategy == "semantic" and self.semantic_splitter is not None:
            try:
                split_docs = self.semantic_splitter.split_documents(documents)
                self._log(
                    "document_split_complete",
                    "语义分块完成",
                    input_documents=len(documents),
                    chunks=len(split_docs),
                    chunk_strategy="semantic",
                    breakpoint_type=Config.SEMANTIC_BREAKPOINT_TYPE,
                    breakpoint_amount=Config.SEMANTIC_BREAKPOINT_AMOUNT,
                )
                return split_docs
            except Exception as exc:
                self._log(
                    "document_split_fallback",
                    "语义分块失败，回退到递归字符分块",
                    error=str(exc),
                )
                # fallback to recursive

        split_docs = self.text_splitter.split_documents(documents)
        self._log(
            "document_split_complete",
            "递归字符分块完成",
            input_documents=len(documents),
            chunks=len(split_docs),
            chunk_strategy="recursive",
        )
        return split_docs
