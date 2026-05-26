"""
加密工具模块：API Key 加密存储、脱敏显示
"""
import hashlib
import os
from base64 import urlsafe_b64encode
from typing import Optional

from cryptography.fernet import Fernet

_fernet: Optional[Fernet] = None


def _derive_key(secret: str, salt: bytes, length: int = 32) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, 100000, dklen=length)


def init_crypto():
    """初始化加密模块：从固定密钥派生 Fernet 密钥，用于 API Key 加密存储。"""
    global _fernet

    secret = os.getenv("RAG_CRYPTO_SECRET", "rag-kb-default-crypto-key")
    salt = b"rag_kb_salt_v1"
    key_material = _derive_key(secret, salt, length=32)
    fernet_raw = urlsafe_b64encode(key_material)
    _fernet = Fernet(fernet_raw)


def encrypt_api_key(plaintext: str) -> str:
    """加密 API Key。"""
    if _fernet is None:
        raise RuntimeError("Crypto module not initialized")
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    """解密 API Key。"""
    if _fernet is None:
        raise RuntimeError("Crypto module not initialized")
    return _fernet.decrypt(ciphertext.encode()).decode()


def mask_value(value: str, visible_start: int = 4, visible_end: int = 4) -> str:
    """脱敏显示：保留首尾各 N 位，中间用 *** 替代。"""
    if not value:
        return ""
    if len(value) <= visible_start + visible_end:
        return value[0] + "***" + value[-1] if len(value) > 2 else "***"
    return value[:visible_start] + "***" + value[-visible_end:]
