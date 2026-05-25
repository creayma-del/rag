"""聊天查询模块：问答、流式查询、对话历史管理。"""

import asyncio
import json
import threading
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import Config
from src.qa_engine import QAEngine, RuntimeRegistry
from src.vector_store import VectorStoreManager
from src.chat_history import ChatHistoryManager, _validate_session_id
from src.trace_logger import new_trace_id, log_pipeline
from dependencies import get_runtime_registry

router = APIRouter(tags=["聊天查询"])


# ---- 请求模型 ----

class QueryRequest(BaseModel):
    question: str
    model: str = Config.DEFAULT_MODEL
    temperature: float = Config.TEMPERATURE
    max_tokens: int = Config.MAX_TOKENS
    top_k: int = Config.TOP_K
    use_reranker: bool = False
    reranker_top_n: int = Config.RERANKER_TOP_N
    session_id: Optional[str] = None


class CreateSessionRequest(BaseModel):
    title: Optional[str] = None


class SessionTitleRequest(BaseModel):
    title: str


# ---- 问答查询 ----

@router.post("/api/query")
async def query(
    request: QueryRequest,
    runtime_registry: RuntimeRegistry = Depends(get_runtime_registry),
):
    """处理问答查询请求。"""
    trace_id = new_trace_id("query")
    try:
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
                embeddings=vector_store_manager.embeddings,
            )
            qa_engine.set_trace(trace_id, "query")
            print(f"🤖 正在使用 {request.model} 生成回答...")

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

            session_id = request.session_id
            if session_id:
                chat_manager = ChatHistoryManager()
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


# ---- 流式查询 ----

@router.get("/api/query/stream")
async def query_stream(
    question: str,
    model: str = Config.DEFAULT_MODEL,
    temperature: float = Config.TEMPERATURE,
    max_tokens: int = Config.MAX_TOKENS,
    top_k: int = Config.TOP_K,
    use_reranker: bool = False,
    reranker_top_n: int = Config.RERANKER_TOP_N,
    session_id: Optional[str] = None,
    runtime_registry: RuntimeRegistry = Depends(get_runtime_registry),
):
    """流式查询（GET）。"""
    if session_id:
        try:
            _validate_session_id(session_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    trace_id = new_trace_id("query_stream")

    async def generate():
        try:
            print(f"🔍 处理流式查询请求，模型: {model}")

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
                embeddings=vector_store_manager.embeddings,
            )
            qa_engine.set_trace(trace_id, "query_stream")

            chat_history = None
            if session_id:
                chat_manager = ChatHistoryManager()
                session = chat_manager.get_session(session_id)
                if session:
                    chat_history = [
                        {"role": msg.role, "content": msg.content}
                        for msg in session.messages
                    ]

            loop = asyncio.get_event_loop()
            chunk_queue: asyncio.Queue = asyncio.Queue()
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
                    done_data = {
                        'done': True,
                        'answer': item['answer'],
                        'retrieval_info': item['retrieval_info'],
                        'rerank_info': item['rerank_info'],
                        'used_reranker': item['used_reranker'],
                        'trace_id': trace_id,
                    }
                    yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"

                    if session_id:
                        chat_manager = ChatHistoryManager()
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


@router.post("/api/query/stream")
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


# ---- 对话历史 ----

@router.post("/api/chat/sessions")
async def create_session(request: CreateSessionRequest):
    """创建新会话。"""
    manager = ChatHistoryManager()
    session = manager.create_session(request.title)
    return {
        "session_id": session.session_id,
        "title": session.title,
        "created_at": session.created_at
    }


@router.get("/api/chat/sessions")
async def list_sessions():
    """获取会话列表。"""
    manager = ChatHistoryManager()
    sessions = manager.list_sessions()
    return {"sessions": sessions}


@router.get("/api/chat/sessions/{session_id}")
async def get_session(session_id: str):
    """获取会话详情。"""
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


@router.put("/api/chat/sessions/{session_id}/title")
async def update_session_title(session_id: str, request: SessionTitleRequest):
    """更新会话标题。"""
    manager = ChatHistoryManager()
    try:
        success = manager.update_session_title(session_id, request.title)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success"}


@router.delete("/api/chat/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话。"""
    manager = ChatHistoryManager()
    try:
        success = manager.delete_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success"}


@router.delete("/api/chat/sessions")
async def clear_all_sessions():
    """清空所有会话。"""
    manager = ChatHistoryManager()
    count = manager.clear_all_sessions()
    return {"status": "success", "deleted_count": count}
