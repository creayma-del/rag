"""
认证模块：JWT Token 生成/验证、密码哈希、API Key 加密存储
"""
import hashlib
import hmac
import os
import secrets
import time
from base64 import urlsafe_b64encode
from typing import Optional

import jwt
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)

# ---- JWT ----

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

_jwt_secret: Optional[str] = None
_fernet_key: Optional[bytes] = None
_fernet: Optional[Fernet] = None
_password_hash: Optional[str] = None


def _derive_key(password: str, salt: bytes, length: int = 32) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000, dklen=length)


def init_auth(password: str):
    """初始化认证模块：从密码派生 JWT 密钥、Fernet 密钥和密码哈希。"""
    global _jwt_secret, _fernet_key, _fernet, _password_hash

    salt = b"rag_kb_salt_v1"
    key_material = _derive_key(password, salt, length=64)
    jwt_key = key_material[:32]
    fernet_raw = key_material[32:]

    _jwt_secret = urlsafe_b64encode(jwt_key).decode()
    _fernet_key = urlsafe_b64encode(fernet_raw)
    _fernet = Fernet(_fernet_key)

    # 密码哈希用于登录校验
    login_salt = os.urandom(16)
    hash_bytes = hashlib.pbkdf2_hmac("sha256", password.encode(), login_salt, 200000)
    _password_hash = login_salt.hex() + ":" + hash_bytes.hex()


def verify_password(password: str) -> bool:
    """验证登录密码。"""
    if _password_hash is None:
        return False
    try:
        salt_hex, hash_hex = _password_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200000)
        return hmac.compare_digest(expected, actual)
    except (ValueError, AttributeError):
        return False


def create_token() -> str:
    """生成 JWT 登录令牌，有效期 24h。"""
    if _jwt_secret is None:
        raise RuntimeError("Auth module not initialized")
    payload = {
        "sub": "admin",
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRY_HOURS * 3600,
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, _jwt_secret, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> bool:
    """验证 JWT 令牌。"""
    if _jwt_secret is None:
        return False
    try:
        jwt.decode(token, _jwt_secret, algorithms=[JWT_ALGORITHM])
        return True
    except jwt.PyJWTError:
        return False


# ---- API Key 加密存储 ----

def encrypt_api_key(plaintext: str) -> str:
    """加密 API Key。"""
    if _fernet is None:
        raise RuntimeError("Auth module not initialized")
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    """解密 API Key。"""
    if _fernet is None:
        raise RuntimeError("Auth module not initialized")
    return _fernet.decrypt(ciphertext.encode()).decode()


def mask_value(value: str, visible_start: int = 4, visible_end: int = 4) -> str:
    """脱敏显示：保留首尾各 N 位，中间用 *** 替代。"""
    if not value:
        return ""
    if len(value) <= visible_start + visible_end:
        return value[0] + "***" + value[-1] if len(value) > 2 else "***"
    return value[:visible_start] + "***" + value[-visible_end:]


# ---- FastAPI 认证依赖 ----

async def require_auth(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """FastAPI 依赖：校验请求是否携带有效 JWT。"""
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    if not verify_token(credentials.credentials):
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return credentials.credentials