"""认证授权模块：登录、Token 验证、认证中间件。"""

import threading
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.auth import verify_password, create_token, require_auth, verify_token

router = APIRouter(prefix="/api/auth", tags=["认证"])


# ---- 登录速率限制 ----

_LOGIN_RATE_WINDOW = 300  # 5 分钟窗口
_LOGIN_MAX_ATTEMPTS = 5   # 窗口内最多 5 次失败
_login_failures: dict[str, list[float]] = defaultdict(list)
_login_lock = threading.Lock()


def _check_login_rate(client_ip: str) -> None:
    """检查登录速率，超限则抛出 429。"""
    now = time.time()
    with _login_lock:
        cutoff = now - _LOGIN_RATE_WINDOW
        _login_failures[client_ip] = [
            t for t in _login_failures[client_ip] if t > cutoff
        ]
        if len(_login_failures[client_ip]) >= _LOGIN_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail=f"登录尝试过于频繁，请 {_LOGIN_RATE_WINDOW // 60} 分钟后再试",
            )


def _record_login_failure(client_ip: str) -> None:
    """记录一次登录失败。"""
    now = time.time()
    with _login_lock:
        _login_failures[client_ip].append(now)


# ---- 请求模型 ----

class LoginRequest(BaseModel):
    password: str


# ---- 路由 ----

@router.post("/login")
async def login(body: LoginRequest, req: Request):
    """使用密码登录，返回 JWT Token。"""
    client_ip = req.client.host if req.client else "unknown"
    _check_login_rate(client_ip)
    if verify_password(body.password):
        token = create_token()
        return {"token": token, "token_type": "bearer"}
    _record_login_failure(client_ip)
    raise HTTPException(status_code=401, detail="密码错误")


@router.get("/verify")
async def verify_auth(_token: str = Depends(require_auth)):
    """验证当前 Token 是否有效。"""
    return {"status": "ok"}


# ---- 认证中间件工厂 ----

def create_auth_middleware(public_paths: set):
    """创建全局认证中间件，除公开路径外需携带有效 JWT。
    支持 Authorization header 或 URL ?token= 参数（SSE 兼容）。"""

    async def auth_middleware(request: Request, call_next):
        if request.url.path in public_paths or request.url.path.startswith("/api/auth/"):
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = request.query_params.get("token")

        if not token or not verify_token(token):
            return JSONResponse(
                status_code=401,
                content={"detail": "未登录，请先登录"},
            )
        return await call_next(request)

    return auth_middleware
