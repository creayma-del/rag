import json
import threading
import time
from typing import Dict, Generator

import requests
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from sentence_transformers import CrossEncoder
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline, TextIteratorStreamer

from config import Config
from src.trace_logger import log_pipeline


class RuntimeRegistry:
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._llm_cache = {}
        self._llm_status = {}
        self._llm_errors = {}
        self._llm_events = {}
        self._reranker_cache = {}
        self._llm_lock = threading.RLock()
        self._reranker_lock = threading.RLock()
        self._initialized = True

    def get_llm(self, model_name, allow_download=False):
        with self._llm_lock:
            if model_name in self._llm_cache:
                print(f"♻️ 复用 LLM 运行时: {model_name}")
                return self._llm_cache[model_name]

            current_status = self._llm_status.get(model_name)
            if current_status == "loading":
                # 模型正在加载中，等待加载完成而不是直接拒绝
                event = self._llm_events.get(model_name, threading.Event())
                self._llm_events[model_name] = event

        if current_status == "loading":
            print(f"⏳ 模型 {model_name} 正在由其他线程加载，等待完成...")
            waited = self._llm_events[model_name].wait(timeout=1800)
            with self._llm_lock:
                if model_name in self._llm_cache:
                    print(f"✅ 模型 {model_name} 已被其他线程加载完成，复用")
                    return self._llm_cache[model_name]
                if not waited:
                    self._llm_status[model_name] = "failed"
                    self._llm_errors[model_name] = "下载超时，请检查网络或 HuggingFace 连接"
                    raise ValueError(
                        f"模型 {model_name} 加载超时（30 分钟），请检查网络连接。"
                        f" 如在国内，建议设置环境变量 HF_ENDPOINT=https://hf-mirror.com 加速下载。"
                    )
                status = self._llm_status.get(model_name)
                if status == "failed":
                    error = self._llm_errors.get(model_name, "未知错误")
                    raise ValueError(f"模型 {model_name} 加载失败: {error}")
                # 加载成功但缓存中仍无（理论上不应发生），继续走下方加载流程

        if model_name.startswith("local") and not allow_download:
            raise ValueError(
                f"本地模型 {model_name} 尚未预热完成，当前问答请求不会自动下载大模型。"
                f" 请先调用 /api/preload 预热该模型，或切换到云端模型/更小的本地模型。"
            )

        with self._llm_lock:
            self._llm_status[model_name] = "loading"
            self._llm_errors.pop(model_name, None)
            event = self._llm_events.setdefault(model_name, threading.Event())
            event.clear()

        try:
            llm_runtime = self._build_llm(
                model_name,
                allow_download=allow_download,
            )
        except Exception as exc:
            with self._llm_lock:
                self._llm_status[model_name] = "failed"
                self._llm_errors[model_name] = str(exc)
                self._llm_events[model_name].set()
            raise

        with self._llm_lock:
            self._llm_cache[model_name] = llm_runtime
            self._llm_status[model_name] = "ready"
            self._llm_events[model_name].set()
            return llm_runtime

    def invalidate_llm(self, model_name):
        with self._llm_lock:
            removed_runtime = self._llm_cache.pop(model_name, None)
            self._llm_status.pop(model_name, None)
            self._llm_errors.pop(model_name, None)
            if removed_runtime is not None:
                print(f"🗑️ 已清理 LLM 运行时缓存: {model_name}")
            return removed_runtime is not None

    def get_llm_status(self, model_name):
        with self._llm_lock:
            return {
                "state": self._llm_status.get(
                    model_name,
                    "ready" if model_name in self._llm_cache else "idle",
                ),
                "cached": model_name in self._llm_cache,
                "error": self._llm_errors.get(model_name),
            }

    def get_reranker(self, enabled):
        if not enabled:
            return None

        reranker_model = Config.RERANKER_MODEL
        with self._reranker_lock:
            if reranker_model in self._reranker_cache:
                print(f"♻️ 复用 Reranker 运行时: {reranker_model}")
                return self._reranker_cache[reranker_model]

            print(f"📥 正在加载 Reranker 模型: {reranker_model}")
            reranker = CrossEncoder(reranker_model)
            print("✅ Reranker 模型加载完成")
            self._reranker_cache[reranker_model] = reranker
            return reranker

    def preload(self, model_name=None, use_reranker=False):
        target_model = model_name or Config.DEFAULT_MODEL
        llm_runtime = self.get_llm(target_model, allow_download=True)
        reranker = self.get_reranker(use_reranker)
        return {
            "model": target_model,
            "llm_runtime": llm_runtime.__class__.__name__,
            "reranker_model": Config.RERANKER_MODEL if reranker else None,
        }

    def _build_llm(self, model_name, allow_download=False):
        model_config = Config.MODEL_CONFIGS.get(model_name)
        if not model_config:
            raise ValueError(f"不支持的模型: {model_name}")

        if model_name.startswith("local"):
            return LocalLLMRuntime(
                model_name=model_name,
                model_config=model_config,
                allow_download=allow_download,
            )
        if model_name == "wenxin":
            return WenxinLLMRuntime()
        return OpenAICompatibleLLMRuntime(model_name, model_config)


class OpenAICompatibleLLMRuntime:
    def __init__(self, model_name, model_config):
        api_key = Config.get_model_api_key(model_name)
        if not api_key or api_key.startswith("your-"):
            raise ValueError(f"请配置 {model_config['api_key_env']} 环境变量")

        print(f"📥 正在初始化 LLM 运行时: {model_name}")
        self.client = ChatOpenAI(
            model_name=model_config["model"],
            api_key=api_key,
            base_url=model_config["api_base"],
        )
        print("✅ LLM 运行时初始化完成")

    def invoke(self, prompt, temperature, max_tokens, chat_history=None):
        runnable = self.client.bind(
            temperature=temperature,
            max_tokens=max_tokens,
        )
        result = runnable.invoke(prompt)
        if hasattr(result, "content"):
            return result.content
        return str(result)

    def stream(self, prompt, temperature, max_tokens, chat_history=None):
        runnable = self.client.bind(
            temperature=temperature,
            max_tokens=max_tokens,
        )
        for chunk in runnable.stream(prompt):
            if hasattr(chunk, "content"):
                yield chunk.content
            else:
                yield str(chunk)


class LocalLLMRuntime:
    def __init__(self, model_name, model_config, allow_download=False):
        self.model_name = model_name
        self.hf_model_name = model_config.get("model", "Qwen/Qwen2-1.5B-Instruct")
        self.allow_download = allow_download
        print(f"📥 正在加载本地 LLM 模型: {self.hf_model_name}")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.hf_model_name,
                local_files_only=not allow_download,
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                self.hf_model_name,
                device_map="cpu",
                torch_dtype="auto",
                low_cpu_mem_usage=True,
                local_files_only=not allow_download,
            )
            self.text_generation = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                pad_token_id=self.tokenizer.eos_token_id,
            )
            print("✅ 本地 LLM 模型加载完成")
        except Exception as exc:
            if not allow_download:
                raise ValueError(
                    f"本地模型 {self.model_name} 尚未预热完成，当前问答请求不会自动下载大模型。"
                    f" 请先调用 /api/preload 预热该模型，或切换到云端模型/更小的本地模型。"
                ) from exc
            error_message = str(exc)
            if "is not a local folder and is not a valid model identifier" in error_message:
                raise ValueError(
                    f"本地模型 {self.model_name} 的 HuggingFace 模型标识无效: {self.hf_model_name}"
                ) from exc
            if "gated repo" in error_message or "401 Client Error" in error_message or "403 Client Error" in error_message:
                raise ValueError(
                    f"本地模型 {self.model_name} 需要 HuggingFace 访问权限。"
                    f" 请先在 HuggingFace 接受 {self.hf_model_name} 的许可证，并执行 huggingface-cli login。"
                ) from exc
            print(f"Failed to load local model {self.hf_model_name}: {exc}")
            raise

    def invoke(self, prompt, temperature, max_tokens, chat_history=None):
        # temperature=0 时使用贪心解码，避免 transformers 报错
        gen_kwargs = dict(
            max_new_tokens=max_tokens,
            top_p=0.95,
            pad_token_id=self.tokenizer.eos_token_id,
            return_full_text=False,
        )
        if temperature and temperature > 0:
            gen_kwargs["temperature"] = temperature
            gen_kwargs["do_sample"] = True
        else:
            gen_kwargs["do_sample"] = False

        outputs = self.text_generation(prompt, **gen_kwargs)
        if isinstance(outputs, list) and len(outputs) > 0:
            result = outputs[0].get("generated_text", "")
        else:
            result = str(outputs)
        return result

    def stream(self, prompt, temperature, max_tokens, chat_history=None):
        from threading import Thread

        inputs = self.tokenizer(prompt, return_tensors="pt")
        streamer = TextIteratorStreamer(
            self.tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )

        generation_kwargs = dict(
            **inputs,
            max_new_tokens=max_tokens,
            top_p=0.95,
            pad_token_id=self.tokenizer.eos_token_id,
            streamer=streamer,
        )
        # temperature=0 时使用贪心解码，避免 transformers 报错
        if temperature and temperature > 0:
            generation_kwargs["temperature"] = temperature
            generation_kwargs["do_sample"] = True
        else:
            generation_kwargs["do_sample"] = False

        thread = Thread(target=self.model.generate, kwargs=generation_kwargs)
        thread.start()

        for new_text in streamer:
            yield new_text


class WenxinLLMRuntime:
    """百度千帆（文心一言）API 运行时。通过 OAuth 2.0 获取 access_token 后调用。"""
    # 提前 5 分钟刷新，避免临界过期
    _TOKEN_REFRESH_BUFFER_SECONDS = 300

    def __init__(self):
        api_key = Config.get_model_api_key("wenxin")
        if not api_key or api_key.startswith("your-"):
            raise ValueError("请配置 WENXIN_API_KEY 环境变量")

        print("📥 正在初始化文心一言运行时")
        self.api_key = api_key
        self.secret_key = Config.WENXIN_SECRET_KEY
        self.api_base = "https://aip.baidubce.com/oauth/2.0/token"
        self.chat_api_base = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions"
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        print("✅ 文心一言运行时初始化完成")

    def _is_token_valid(self) -> bool:
        """检查缓存的 token 是否有效且未过期（含提前刷新窗口）。"""
        return (
            self._access_token is not None
            and time.time() < self._token_expires_at - self._TOKEN_REFRESH_BUFFER_SECONDS
        )

    def _fetch_access_token(self) -> str:
        """向百度 OAuth 接口请求新的 access_token。"""
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key,
        }

        response = requests.post(self.api_base, params=params)
        response.raise_for_status()
        data = response.json()

        access_token = data.get("access_token")
        if not access_token:
            error_desc = data.get("error_description", data.get("error", "未知错误"))
            raise ValueError(f"获取文心一言 access_token 失败: {error_desc}")

        expires_in = int(data.get("expires_in", 2592000))
        self._access_token = access_token
        self._token_expires_at = time.time() + expires_in
        print(f"✅ 文心一言 access_token 已刷新，有效期 {expires_in // 86400} 天")
        return access_token

    def _get_access_token(self) -> str:
        """获取有效的 access_token，过期自动刷新。"""
        if self._is_token_valid():
            return self._access_token  # type: ignore[return-value]

        return self._fetch_access_token()

    def _handle_unauthorized(self) -> None:
        """收到 401/403 时强制清除 token 缓存，下次调用自动刷新。"""
        self._access_token = None
        self._token_expires_at = 0.0

    def _build_messages(self, prompt, chat_history=None):
        """构建文心一言 API 的 messages 数组。
        如果传入了 chat_history，使用原生多轮对话格式；
        否则回退到单条 user 消息。"""
        if chat_history:
            messages = []
            for msg in chat_history[-10:]:  # 最近 10 轮
                role = "user" if msg.get("role") == "user" else "assistant"
                content = msg.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})
            # 追加当前 prompt 作为最新的 user 消息
            messages.append({"role": "user", "content": prompt})
            return messages
        return [{"role": "user", "content": str(prompt)}]

    def invoke(self, prompt, temperature, max_tokens, chat_history=None):
        access_token = self._get_access_token()
        messages = self._build_messages(prompt, chat_history)
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = requests.post(
            f"{self.chat_api_base}?access_token={access_token}",
            json=payload,
        )

        # token 过期时自动刷新并重试一次
        if response.status_code in (401, 403):
            self._handle_unauthorized()
            access_token = self._get_access_token()
            response = requests.post(
                f"{self.chat_api_base}?access_token={access_token}",
                json=payload,
            )

        response.raise_for_status()
        data = response.json()
        return data.get("result", "")
    
    def stream(self, prompt, temperature, max_tokens, chat_history=None):
        access_token = self._get_access_token()
        messages = self._build_messages(prompt, chat_history)
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        response = requests.post(
            f"{self.chat_api_base}?access_token={access_token}",
            json=payload,
            stream=True,
            headers={"Accept": "text/event-stream"},
        )

        # token 过期时自动刷新并重试一次
        if response.status_code in (401, 403):
            response.close()
            self._handle_unauthorized()
            access_token = self._get_access_token()
            response = requests.post(
                f"{self.chat_api_base}?access_token={access_token}",
                json=payload,
                stream=True,
                headers={"Accept": "text/event-stream"},
            )

        response.raise_for_status()

        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if not data_str:
                continue
            try:
                data = json.loads(data_str)
                chunk_text = data.get("result", "")
                if chunk_text:
                    yield chunk_text
                if data.get("is_end"):
                    break
            except json.JSONDecodeError:
                continue


class QAEngine:
    def __init__(
        self,
        vector_store,
        model_name=None,
        temperature=None,
        max_tokens=None,
        top_k=None,
        use_reranker=False,
        reranker_top_n=None,
        runtime_registry=None,
        embeddings=None,
    ):
        self.vector_store = vector_store
        self.embeddings = embeddings
        self.model_name = model_name if model_name is not None else Config.DEFAULT_MODEL
        self.temperature = temperature if temperature is not None else Config.TEMPERATURE
        self.max_tokens = max_tokens if max_tokens is not None else Config.MAX_TOKENS
        self.top_k = top_k if top_k is not None else Config.TOP_K
        self.use_reranker = use_reranker
        self.reranker_top_n = reranker_top_n if reranker_top_n is not None else Config.RERANKER_TOP_N
        self.runtime_registry = runtime_registry or RuntimeRegistry()
        self.trace_id = None
        self.chain = "query"
        self.prompt_template = PromptTemplate(
            input_variables=["context", "question", "history"],
            template=(
                "基于上下文和对话历史回答问题。\n"
                "{history}"
                "上下文：\n{context}\n\n"
                "问题：{question}\n"
                "答案："
            ),
        )

    def set_trace(self, trace_id, chain="query"):
        self.trace_id = trace_id
        self.chain = chain

    def _log(self, stage, message, **details):
        if self.trace_id:
            log_pipeline(self.trace_id, self.chain, stage, message, **details)

    def _rerank_documents(self, query, docs):
        reranker = self.runtime_registry.get_reranker(self.use_reranker)
        if reranker is None:
            self._log(
                "reranker_skip",
                "未启用 Reranker，跳过重排",
                input_documents=len(docs),
            )
            return docs, []

        pairs = [(query, doc.page_content) for doc in docs]
        self._log(
            "reranker_start",
            "开始执行 Reranker 重排",
            input_documents=len(docs),
            reranker_top_n=self.reranker_top_n,
        )
        scores = reranker.predict(pairs)
        scored_docs = list(zip(docs, scores))
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        reranked_docs = [doc for doc, _ in scored_docs[:self.reranker_top_n]]
        rerank_info = [
            {
                "index": idx,
                "source": doc.metadata.get("source", "unknown"),
                "score": float(score),
                "content_preview": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
            }
            for idx, (doc, score) in enumerate(scored_docs[:self.reranker_top_n])
        ]
        
        print(f"🔄 Reranker 完成: 从 {len(docs)} 个文档中选择 {len(reranked_docs)} 个最相关文档")
        self._log(
            "reranker_complete",
            "Reranker 重排完成",
            input_documents=len(docs),
            output_documents=len(reranked_docs),
            top_scores=[float(score) for _, score in scored_docs[:self.reranker_top_n]],
        )
        return reranked_docs, rerank_info

    def _format_history(self, chat_history=None):
        if not chat_history:
            return ""
        lines = ["对话历史："]
        for msg in chat_history[-10:]:  # 最近 10 轮
            role_label = "用户" if msg["role"] == "user" else "AI"
            content = msg.get("content", "")
            # 截断过长消息
            if len(content) > 500:
                content = content[:500] + "..."
            lines.append(f"{role_label}：{content}")
        lines.append("")
        return "\n".join(lines)

    def _retrieve_and_assemble_prompt(self, question, chat_history=None):
        """检索 + 重排 + 拼装 prompt，get_answer 和 stream_answer 共用。
        返回 (prompt, retrieval_info, rerank_info, pipeline_stages)。"""
        import time as _time
        pipeline_stages = []

        # ── 阶段 1: Query Encoder 查询编码 ──
        t0 = _time.time()
        self._log(
            "retrieval_start",
            "开始向量检索",
            question=question,
            top_k=self.top_k,
            model=self.model_name,
        )

        if self.embeddings is None:
            raise ValueError("Embeddings 模型未加载，无法执行查询向量化")
        query_vector = self.embeddings.embed_query(question)
        query_encode_ms = round((_time.time() - t0) * 1000, 1)
        self._log(
            "query_encoding_complete",
            "查询向量化完成（Query Encoder 独立步骤）",
            question=question,
            query_vector_dimension=len(query_vector),
            embedding_model=Config.EMBEDDING_MODEL,
        )
        pipeline_stages.append({
            "name": "query_encoding",
            "label": "Query Encoder 查询编码",
            "description": "将用户问题通过 Embedding 模型转换为向量表示",
            "input": {"question": question},
            "output": {
                "query_vector_dimension": len(query_vector),
                "embedding_model": Config.EMBEDDING_MODEL,
            },
            "duration_ms": query_encode_ms,
        })

        # ── 阶段 2: Retriever 向量检索 ──
        t0 = _time.time()
        results = self.vector_store._collection.query(
            query_embeddings=[query_vector],
            n_results=self.top_k,
            include=["documents", "metadatas", "distances"],
        )

        docs_with_scores = []
        if results and results.get("ids") and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                content = (results["documents"][0][i]
                           if results.get("documents") and results["documents"][0] else "")
                metadata = (results["metadatas"][0][i]
                            if results.get("metadatas") and results["metadatas"][0] else {})
                distance = (results["distances"][0][i]
                            if results.get("distances") and results["distances"][0] else 0.0)
                doc = Document(page_content=content, metadata=metadata)
                docs_with_scores.append((doc, distance))

        docs = [doc for doc, _ in docs_with_scores]

        retrieval_info = [
            {
                "index": idx,
                "source": doc.metadata.get("source", "unknown"),
                "score": round(1.0 - float(distance), 4),
                "content_preview": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                "content": doc.page_content,
            }
            for idx, (doc, distance) in enumerate(docs_with_scores)
        ]
        retrieval_ms = round((_time.time() - t0) * 1000, 1)

        self._log(
            "retrieval_complete",
            "向量检索完成",
            question=question,
            retrieved_documents=len(docs),
            sources=[doc.metadata.get("source") for doc in docs],
        )
        pipeline_stages.append({
            "name": "retrieval",
            "label": "Retriever 向量检索",
            "description": "使用查询向量在向量库中进行相似度检索，返回 Top-K 相关文档片段",
            "input": {"top_k": self.top_k, "distance_function": "cosine"},
            "output": {
                "retrieved_count": len(docs),
                "sources": [doc.metadata.get("source") for doc in docs],
                "scores": [round(1.0 - float(d), 4) for _, d in docs_with_scores],
            },
            "duration_ms": retrieval_ms,
        })

        # ── 阶段 3: Reranker 重排序（可选） ──
        rerank_info = []
        if self.use_reranker and docs:
            t0 = _time.time()
            docs, rerank_info = self._rerank_documents(question, docs)
            rerank_ms = round((_time.time() - t0) * 1000, 1)
            pipeline_stages.append({
                "name": "reranking",
                "label": "Reranker 重排序",
                "description": "使用 CrossEncoder 对检索结果进行精排，提升文档相关性",
                "input": {"documents_count": len(retrieval_info), "reranker_top_n": self.reranker_top_n},
                "output": {
                    "reranked_count": len(rerank_info),
                    "top_scores": [r["score"] for r in rerank_info[:3]],
                },
                "duration_ms": rerank_ms,
            })

        # ── 阶段 4: Prompt Builder 提示构建 ──
        t0 = _time.time()
        context = "\n\n".join([doc.page_content for doc in docs])
        history_text = self._format_history(chat_history)
        prompt = self.prompt_template.format(context=context, question=question, history=history_text)
        prompt_ms = round((_time.time() - t0) * 1000, 1)
        self._log(
            "prompt_assemble_complete",
            "提示词拼装完成",
            context_documents=len(docs),
            context_characters=len(context),
            prompt_characters=len(prompt),
        )
        pipeline_stages.append({
            "name": "prompt_building",
            "label": "Prompt Builder 提示构建",
            "description": "将检索到的文档片段、对话历史和用户问题组装为结构化 Prompt",
            "input": {
                "context_documents": len(docs),
                "has_history": bool(chat_history),
            },
            "output": {
                "context_characters": len(context),
                "prompt_characters": len(prompt),
                "prompt_template": self.prompt_template.template,
            },
            "duration_ms": prompt_ms,
        })

        return prompt, retrieval_info, rerank_info, pipeline_stages

    def get_answer(self, question, chat_history=None):
        import time as _time
        prompt, retrieval_info, rerank_info, pipeline_stages = self._retrieve_and_assemble_prompt(question, chat_history)

        llm_runtime = self.runtime_registry.get_llm(self.model_name)
        self._log(
            "llm_invoke_start",
            "开始调用 LLM 生成答案",
            model=self.model_name,
            runtime_class=llm_runtime.__class__.__name__,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        t0 = _time.time()
        answer = llm_runtime.invoke(
            prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            chat_history=chat_history,
        )
        llm_ms = round((_time.time() - t0) * 1000, 1)

        if "答案：" in answer:
            answer = answer.split("答案：", 1)[1].strip()

        self._log(
            "llm_invoke_complete",
            "LLM 回答生成完成",
            answer_characters=len(answer),
        )

        # ── 阶段 5: LLM 答案生成 ──
        pipeline_stages.append({
            "name": "llm_generation",
            "label": "LLM 答案生成",
            "description": "将结构化 Prompt 发送给大语言模型，生成最终答案",
            "input": {
                "model": self.model_name,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "prompt_characters": len(prompt),
            },
            "output": {
                "answer_characters": len(answer),
            },
            "duration_ms": llm_ms,
        })
        
        return {
            "answer": answer,
            "retrieval_info": retrieval_info,
            "rerank_info": rerank_info,
            "used_reranker": self.use_reranker,
            "pipeline_stages": pipeline_stages,
        }

    def stream_answer(self, question, chat_history=None) -> Generator[str, None, Dict]:
        import time as _time
        prompt, retrieval_info, rerank_info, pipeline_stages = self._retrieve_and_assemble_prompt(question, chat_history)

        llm_runtime = self.runtime_registry.get_llm(self.model_name)
        
        full_answer = ""
        prefix_skipped = False
        prefix_buffer = ""
        PREFIX_MAX_BUFFER = 50  # 超过此长度仍未匹配，判定模型未输出前缀

        for chunk in llm_runtime.stream(
            prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            chat_history=chat_history,
        ):
            if not prefix_skipped:
                prefix_buffer += chunk
                idx = prefix_buffer.find("答案：")
                if idx != -1:
                    prefix_skipped = True
                    clean_chunk = prefix_buffer[idx + 3:]
                    if clean_chunk:
                        full_answer += clean_chunk
                        yield clean_chunk
                elif len(prefix_buffer) > PREFIX_MAX_BUFFER:
                    # 模型未输出 "答案：" 前缀，直接输出所有缓冲内容
                    prefix_skipped = True
                    full_answer += prefix_buffer
                    yield prefix_buffer
                    prefix_buffer = ""
            else:
                full_answer += chunk
                yield chunk
        
        if "答案：" in full_answer:
            full_answer = full_answer.split("答案：", 1)[1].strip()

        # ── 阶段 5: LLM 答案生成 ──
        pipeline_stages.append({
            "name": "llm_generation",
            "label": "LLM 答案生成",
            "description": "将结构化 Prompt 发送给大语言模型，生成最终答案",
            "input": {
                "model": self.model_name,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "prompt_characters": len(prompt),
            },
            "output": {
                "answer_characters": len(full_answer),
            },
            "duration_ms": None,  # 流式无法精确计时
        })

        yield {
            "answer": full_answer,
            "retrieval_info": retrieval_info,
            "rerank_info": rerank_info,
            "used_reranker": self.use_reranker,
            "pipeline_stages": pipeline_stages,
        }

    def get_context(self, question):
        if self.embeddings is None:
            raise ValueError("Embeddings 模型未加载，无法执行查询向量化")
        query_vector = self.embeddings.embed_query(question)
        results = self.vector_store._collection.query(
            query_embeddings=[query_vector],
            n_results=self.top_k,
            include=["documents", "metadatas"],
        )
        docs = []
        if results and results.get("ids") and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                content = (results["documents"][0][i]
                           if results.get("documents") and results["documents"][0] else "")
                metadata = (results["metadatas"][0][i]
                            if results.get("metadatas") and results["metadatas"][0] else {})
                docs.append(Document(page_content=content, metadata=metadata))
        return docs

