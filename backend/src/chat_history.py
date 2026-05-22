
import json
import os
import re
import tempfile
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from config import Config

# UUID v4 格式正则
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _validate_session_id(session_id: str) -> None:
    """校验 session_id 是否为合法 UUID 格式，防止路径遍历攻击。"""
    if not _UUID_RE.match(session_id):
        raise ValueError(f"非法 session_id: {session_id!r}")


class ChatMessage:
    def __init__(self, role: str, content: str, timestamp: Optional[str] = None,
                 retrieval_info: Optional[List[Dict]] = None,
                 rerank_info: Optional[List[Dict]] = None):
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now().isoformat()
        self.retrieval_info = retrieval_info or []
        self.rerank_info = rerank_info or []


class ChatSession:
    def __init__(self, session_id: str, title: Optional[str] = None, created_at: Optional[str] = None):
        self.session_id = session_id
        self.title = title or f"对话 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.messages: List[ChatMessage] = []


class ChatHistoryManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._data_dir = Path(Config.PROJECT_ROOT) / "data" / "chat_history"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        # 每个 session_id 一把锁，防止同一会话并发写入导致数据丢失
        self._session_locks: Dict[str, threading.Lock] = {}
        self._locks_lock = threading.Lock()
    
    def _get_session_path(self, session_id: str) -> Path:
        _validate_session_id(session_id)
        return self._data_dir / f"{session_id}.json"

    def _get_session_lock(self, session_id: str) -> threading.Lock:
        """获取指定会话的锁，按需创建。"""
        with self._locks_lock:
            if session_id not in self._session_locks:
                self._session_locks[session_id] = threading.Lock()
            return self._session_locks[session_id]
    
    def _load_session(self, session_id: str) -> Optional[ChatSession]:
        session_path = self._get_session_path(session_id)
        if not session_path.exists():
            return None
        
        try:
            data = json.loads(session_path.read_text(encoding="utf-8"))
            session = ChatSession(
                session_id=data["session_id"],
                title=data["title"],
                created_at=data["created_at"]
            )
            session.updated_at = data.get("updated_at", session.created_at)
            
            for msg_data in data.get("messages", []):
                session.messages.append(ChatMessage(
                    role=msg_data["role"],
                    content=msg_data["content"],
                    timestamp=msg_data.get("timestamp"),
                    retrieval_info=msg_data.get("retrieval_info", []),
                    rerank_info=msg_data.get("rerank_info", []),
                ))
            return session
        except Exception:
            return None
    
    def _save_session(self, session: ChatSession):
        session.updated_at = datetime.now().isoformat()
        session_path = self._get_session_path(session.session_id)

        data = {
            "session_id": session.session_id,
            "title": session.title,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp,
                    "retrieval_info": msg.retrieval_info,
                    "rerank_info": msg.rerank_info,
                }
                for msg in session.messages
            ]
        }

        # 原子写入：先写临时文件，再 rename，防止崩溃时数据丢失
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=self._data_dir, suffix='.tmp', prefix=f'.{session.session_id}_'
        )
        try:
            with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # os.replace 是原子操作（同一文件系统）
            os.replace(tmp_path, session_path)
        except Exception:
            # 清理临时文件
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    
    def create_session(self, title: Optional[str] = None) -> ChatSession:
        import uuid
        session_id = str(uuid.uuid4())
        session = ChatSession(session_id, title)
        self._save_session(session)
        return session
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        return self._load_session(session_id)
    
    def list_sessions(self) -> List[Dict]:
        sessions = []
        for file_path in self._data_dir.glob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                sessions.append({
                    "session_id": data["session_id"],
                    "title": data["title"],
                    "created_at": data["created_at"],
                    "updated_at": data.get("updated_at", data["created_at"]),
                    "message_count": len(data.get("messages", []))
                })
            except Exception:
                continue
        
        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        return sessions
    
    def add_message(self, session_id: str, role: str, content: str,
                     retrieval_info: Optional[List[Dict]] = None,
                     rerank_info: Optional[List[Dict]] = None) -> Optional[ChatSession]:
        lock = self._get_session_lock(session_id)
        with lock:
            session = self._load_session(session_id)
            if not session:
                return None

            session.messages.append(ChatMessage(role, content,
                                                retrieval_info=retrieval_info,
                                                rerank_info=rerank_info))
            self._save_session(session)
            return session
    
    def update_session_title(self, session_id: str, title: str) -> bool:
        lock = self._get_session_lock(session_id)
        with lock:
            session = self._load_session(session_id)
            if not session:
                return False

            session.title = title
            self._save_session(session)
            return True

    def replace_last_ai_message(self, session_id: str, content: str,
                                retrieval_info=None, rerank_info=None) -> Optional[ChatSession]:
        """替换会话中最后一条 AI 消息的内容（用于重新生成场景）。"""
        lock = self._get_session_lock(session_id)
        with lock:
            session = self._load_session(session_id)
            if not session:
                return None
            # 从后往前找到最后一条 AI 消息
            for i in range(len(session.messages) - 1, -1, -1):
                if session.messages[i].role == "ai":
                    session.messages[i].content = content
                    session.messages[i].retrieval_info = retrieval_info or []
                    session.messages[i].rerank_info = rerank_info or []
                    session.messages[i].timestamp = datetime.now().isoformat()
                    self._save_session(session)
                    return session
            return None

    def is_last_user_message(self, session_id: str, content: str) -> bool:
        """检查指定内容是否与会话中最后一条 user 消息相同（用于判断是否为重新生成）。"""
        session = self._load_session(session_id)
        if not session or not session.messages:
            return False
        for i in range(len(session.messages) - 1, -1, -1):
            if session.messages[i].role == "user":
                return session.messages[i].content == content
        return False

    def auto_title_from_question(self, session_id: str, question: str) -> Optional[str]:
        """根据首条问题自动生成会话标题。"""
        lock = self._get_session_lock(session_id)
        with lock:
            session = self._load_session(session_id)
            if not session:
                return None
            # 仅当标题仍是默认格式时才自动生成
            if session.title and not session.title.startswith("对话 "):
                return None

            # 截取问题前 30 个字符，在自然边界处截断
            text = question.strip()
            if len(text) <= 30:
                title = text
            else:
                truncated = text[:30]
                # 尝试在最后一个完整字符处截断
                last_space = truncated.rfind(" ")
                last_punct = max(
                    truncated.rfind("，"), truncated.rfind("。"),
                    truncated.rfind("？"), truncated.rfind("！"),
                    truncated.rfind(","), truncated.rfind("."),
                )
                cut = max(last_space, last_punct)
                title = truncated[:cut] if cut > 0 else truncated

            session.title = title
            self._save_session(session)
            return title
    
    def delete_session(self, session_id: str) -> bool:
        session_path = self._get_session_path(session_id)
        if session_path.exists():
            session_path.unlink()
            return True
        return False
    
    def clear_all_sessions(self) -> int:
        count = 0
        for file_path in self._data_dir.glob("*.json"):
            file_path.unlink()
            count += 1
        return count

