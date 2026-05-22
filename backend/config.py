import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
ENV_FILE = BACKEND_DIR / ".env"
DATA_DIR = PROJECT_ROOT / "data"

load_dotenv(ENV_FILE)


def _resolve_project_path(value, default_relative_path):
    raw_value = value if value not in (None, "") else default_relative_path
    candidate = Path(str(raw_value).strip()).expanduser()
    if not candidate.is_absolute():
        candidate = (PROJECT_ROOT / candidate).resolve()
    return str(candidate)


def _parse_csv_env(value, default_values):
    raw = value if value not in (None, "") else ",".join(default_values)
    items = [item.strip() for item in str(raw).split(",")]
    return tuple(item for item in items if item)


class Config:
    BACKEND_DIR = str(BACKEND_DIR)
    PROJECT_ROOT = str(PROJECT_ROOT)
    ENV_FILE = str(ENV_FILE)

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
    ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "")
    KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
    WENXIN_API_KEY = os.getenv("WENXIN_API_KEY", "")
    WENXIN_SECRET_KEY = os.getenv("WENXIN_SECRET_KEY", "")
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
    BAICHUAN_API_KEY = os.getenv("BAICHUAN_API_KEY", "")
    STEPFUN_API_KEY = os.getenv("STEPFUN_API_KEY", "")
    
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "qwen")
    
    VECTOR_DB_PATH = _resolve_project_path(
        os.getenv("VECTOR_DB_PATH"),
        "data/chroma",
    )
    DOCUMENTS_PATH = _resolve_project_path(
        os.getenv("DOCUMENTS_PATH"),
        "documents",
    )
    MODEL_NAME = os.getenv("MODEL_NAME", "all-MiniLM-L6-v2")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", 4096))
    TEMPERATURE = float(os.getenv("TEMPERATURE", 0.1))

    CHUNK_SIZE = 500
    CHUNK_OVERLAP = 50
    TOP_K = 5
    RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-base")
    RERANKER_TOP_N = int(os.getenv("RERANKER_TOP_N", 3))
    BACKGROUND_PRELOAD_ENABLED = os.getenv("BACKGROUND_PRELOAD_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    BACKGROUND_PRELOAD_DELAY_SECONDS = int(os.getenv("BACKGROUND_PRELOAD_DELAY_SECONDS", 15))
    BACKGROUND_PRELOAD_USE_RERANKER = os.getenv(
        "BACKGROUND_PRELOAD_USE_RERANKER",
        "false",
    ).strip().lower() in {"1", "true", "yes", "on"}
    BACKGROUND_PRELOAD_MODELS = _parse_csv_env(
        os.getenv("BACKGROUND_PRELOAD_MODELS"),
        ("local-huge",),
    )
    SUPPORTED_DOCUMENT_EXTENSIONS = {
        ".txt",
        ".md",
        ".markdown",
        ".pdf",
        ".docx",
        ".csv",
        ".json",
        ".html",
        ".htm",
        ".xml",
        ".yml",
        ".yaml",
        ".zip",
    }
    ARCHIVE_SUPPORTED_EXTENSIONS = {".zip"}
    ARCHIVE_MAX_MEMBERS = int(os.getenv("ARCHIVE_MAX_MEMBERS", 200))
    ARCHIVE_MAX_UNCOMPRESSED_BYTES = int(
        os.getenv("ARCHIVE_MAX_UNCOMPRESSED_BYTES", 100 * 1024 * 1024)
    )
    AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "admin").strip()
    INDEX_STATE_FILENAME = "_index_state.json"
    
    MODEL_CONFIGS = {
        "openai": {
            "api_base": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "api_key_env": "OPENAI_API_KEY",
            "description": "OpenAI GPT-4o Mini，性价比高"
        },
        "qwen": {
            "api_base": "https://dashscope.aliyuncs.com/api/compatible-mode/v1",
            "model": "qwen-plus",
            "api_key_env": "QWEN_API_KEY",
            "description": "阿里通义千问 Qwen-Plus"
        },
        "zhipu": {
            "api_base": "https://open.bigmodel.cn/api/paas/v4",
            "model": "glm-4-flash",
            "api_key_env": "ZHIPU_API_KEY",
            "description": "智谱 GLM-4-Flash，快速推理"
        },
        "kimi": {
            "api_base": "https://api.moonshot.cn/v1",
            "model": "moonshot-v1-8k",
            "api_key_env": "KIMI_API_KEY",
            "description": "月之暗面 Kimi，超长上下文"
        },
        "deepseek": {
            "api_base": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key_env": "DEEPSEEK_API_KEY",
            "description": "DeepSeek-V3，国产顶流"
        },
        "siliconflow": {
            "api_base": "https://api.siliconflow.cn/v1",
            "model": "deepseek-ai/DeepSeek-V3",
            "api_key_env": "SILICONFLOW_API_KEY",
            "description": "硅基流动，模型聚合平台"
        },
        "groq": {
            "api_base": "https://api.groq.com/openai/v1",
            "model": "llama-3.3-70b-versatile",
            "api_key_env": "GROQ_API_KEY",
            "description": "Groq LPU 极速推理"
        },
        "mistral": {
            "api_base": "https://api.mistral.ai/v1",
            "model": "mistral-small-latest",
            "api_key_env": "MISTRAL_API_KEY",
            "description": "Mistral AI，欧洲领先"
        },
        "baichuan": {
            "api_base": "https://api.baichuan-ai.com/v1",
            "model": "Baichuan4-Air",
            "api_key_env": "BAICHUAN_API_KEY",
            "description": "百川智能 Baichuan4-Air"
        },
        "stepfun": {
            "api_base": "https://api.stepfun.com/v1",
            "model": "step-2-16k",
            "api_key_env": "STEPFUN_API_KEY",
            "description": "阶跃星辰 Step-2"
        },
        "wenxin": {
            "api_base": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions",
            "model": "completions",
            "api_key_env": "WENXIN_API_KEY",
            "secret_key_env": "WENXIN_SECRET_KEY",
            "description": "百度文心一言（需配置 Secret Key）"
        },
        "local": {
            "model": "Qwen/Qwen2-1.5B-Instruct"
        },
        "local-small": {
            "model": "Qwen/Qwen2-0.5B-Instruct",
            "description": "0.5B 参数，适合低配置设备"
        },
        "local-medium": {
            "model": "Qwen/Qwen2.5-3B-Instruct",
            "description": "3B 参数，平衡性能与效果"
        },
        "local-large": {
            "model": "Qwen/Qwen2-7B-Instruct",
            "description": "7B 参数，效果更好，需要更多内存"
        },
        "local-huge": {
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "description": "Qwen 2.5 7B，大模型，建议通过后台延迟预热加载"
        }
    }

    @classmethod
    def get_env_value(cls, env_var, default=""):
        value = os.getenv(env_var, default)
        if isinstance(value, str):
            return value.strip()
        return value

    @classmethod
    def get_model_config(cls, model_name):
        return cls.MODEL_CONFIGS.get(model_name)

    # 占位值模式：匹配 "your-xxx-api-key" / "your-xxx-secret-key" 等默认占位
    _PLACEHOLDER_PREFIX = "your-"

    @classmethod
    def get_model_api_key(cls, model_name):
        model_config = cls.get_model_config(model_name)
        if not model_config:
            return ""

        env_var = model_config.get("api_key_env")
        if not env_var:
            return ""

        value = cls.get_env_value(env_var)
        # 过滤占位值（如 "your-openai-api-key"），这些不是真实密钥
        if value and value.lower().startswith(cls._PLACEHOLDER_PREFIX):
            return ""
        return value

    @classmethod
    def set_model_api_key(cls, model_name, api_key):
        model_config = cls.get_model_config(model_name)
        if not model_config or "api_key_env" not in model_config:
            raise ValueError(f"模型 {model_name} 不支持 API Key 配置")

        cleaned_api_key = (api_key or "").strip()
        env_var = model_config["api_key_env"]
        os.environ[env_var] = cleaned_api_key
        setattr(cls, env_var, cleaned_api_key)

        # 加密后持久化到独立文件
        cls._save_encrypted_keys()
        return env_var

    _encrypted_keys_path: Optional[str] = None

    @classmethod
    def _get_encrypted_keys_path(cls):
        if cls._encrypted_keys_path is not None:
            return cls._encrypted_keys_path
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls._encrypted_keys_path = str(DATA_DIR / "encrypted_keys.json")
        return cls._encrypted_keys_path

    @classmethod
    def _load_encrypted_keys(cls):
        """启动时从加密文件加载 API Keys 到 os.environ。
        如果某个 Key 在 os.environ 中已被显式设为空字符串（表示用户已清除），
        则不从文件恢复，防止已删除的 Key 复活。"""
        try:
            from src.auth import decrypt_api_key
        except ImportError:
            return
        keys_path = cls._get_encrypted_keys_path()
        if not os.path.exists(keys_path):
            return
        try:
            with open(keys_path, "r", encoding="utf-8") as f:
                encrypted_data = json.load(f)
            for key_name, ciphertext in encrypted_data.items():
                # 处理 secret_key 后缀条目（如 "wenxin__secret"）
                if key_name.endswith("__secret"):
                    model_name = key_name[:-len("__secret")]
                    model_config = cls.get_model_config(model_name)
                    if not model_config:
                        continue
                    secret_env_var = model_config.get("secret_key_env")
                    if not secret_env_var:
                        continue
                    if secret_env_var in os.environ and os.environ[secret_env_var] == "":
                        continue
                    try:
                        raw_key = decrypt_api_key(ciphertext)
                        os.environ[secret_env_var] = raw_key
                        setattr(cls, secret_env_var, raw_key)
                    except Exception:
                        pass
                    continue
                # 处理普通 api_key 条目
                model_config = cls.get_model_config(key_name)
                if not model_config:
                    continue
                env_var = model_config.get("api_key_env")
                if env_var:
                    if env_var in os.environ and os.environ[env_var] == "":
                        continue
                    try:
                        raw_key = decrypt_api_key(ciphertext)
                        os.environ[env_var] = raw_key
                        setattr(cls, env_var, raw_key)
                    except Exception:
                        pass
        except (json.JSONDecodeError, OSError):
            pass

    @classmethod
    def _save_encrypted_keys(cls):
        """加密保存当前所有已配置的 API Keys（含 secret_key_env）。"""
        try:
            from src.auth import encrypt_api_key
        except ImportError:
            return
        encrypted_data = {}
        for model_name in cls.MODEL_CONFIGS:
            model_config = cls.get_model_config(model_name)
            if not model_config:
                continue
            # 保存 api_key_env 对应的密钥
            raw_key = cls.get_model_api_key(model_name)
            if raw_key:
                try:
                    encrypted_data[model_name] = encrypt_api_key(raw_key)
                except Exception:
                    continue
            # 保存 secret_key_env 对应的密钥（如 WENXIN_SECRET_KEY）
            secret_env_var = model_config.get("secret_key_env")
            if secret_env_var:
                secret_key = cls.get_env_value(secret_env_var)
                if secret_key and not secret_key.lower().startswith(cls._PLACEHOLDER_PREFIX):
                    try:
                        encrypted_data[f"{model_name}__secret"] = encrypt_api_key(secret_key)
                    except Exception:
                        continue
        keys_path = cls._get_encrypted_keys_path()
        if not encrypted_data:
            # 所有 Key 都已清除，删除加密文件防止旧 Key 复活
            if os.path.exists(keys_path):
                try:
                    os.remove(keys_path)
                except OSError:
                    pass
            return
        try:
            with open(keys_path, "w", encoding="utf-8") as f:
                json.dump(encrypted_data, f, ensure_ascii=False)
        except OSError:
            pass

    @classmethod
    def get_model_api_key_masked(cls, model_name: str) -> str:
        """返回脱敏后的 API Key，供前端展示。"""
        raw_key = cls.get_model_api_key(model_name)
        if not raw_key:
            return ""
        from src.auth import mask_value
        return mask_value(raw_key)

    _config_file_path = None
    _persistent_keys = {
        "CHUNK_SIZE", "CHUNK_OVERLAP", "EMBEDDING_MODEL", "RERANKER_MODEL",
        "MAX_TOKENS", "TEMPERATURE", "TOP_K", "RERANKER_TOP_N",
    }

    @classmethod
    def _get_config_file_path(cls):
        if cls._config_file_path is not None:
            return cls._config_file_path
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls._config_file_path = str(DATA_DIR / "runtime_config.json")
        return cls._config_file_path

    @classmethod
    def _load_runtime_config(cls):
        config_path = cls._get_config_file_path()
        if not os.path.exists(config_path):
            return
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, value in data.items():
                if key in cls._persistent_keys and hasattr(cls, key):
                    setattr(cls, key, value)
        except (json.JSONDecodeError, OSError):
            pass

    @classmethod
    def _save_runtime_config(cls):
        config_path = cls._get_config_file_path()
        data = {}
        for key in cls._persistent_keys:
            if hasattr(cls, key):
                data[key] = getattr(cls, key)
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    @classmethod
    def save_config(cls):
        """供 API 层调用，持久化当前运行时的配置。"""
        cls._save_runtime_config()


# 服务启动时加载持久化配置
Config._load_runtime_config()
