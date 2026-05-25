"""知识库 RAG API - 主入口文件。

负责应用初始化、中间件配置和路由注册。
业务逻辑已拆分到各子模块中。
"""

import os

# 禁用 langchain 遥测，避免 posthog capture() 兼容性报错
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGCHAIN_TELEMETRY", "false")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import Config
from src.auth import init_auth
from src.qa_engine import RuntimeRegistry

# 导入各业务模块路由
from auth_api import router as auth_router, create_auth_middleware
from documents_api import router as documents_router
from vector_store_api import router as vector_store_router
from models_api import router as models_router, schedule_background_preload
from chat_api import router as chat_router
from system_api import router as system_router

# 创建应用
app = FastAPI(title="知识库 RAG API")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 免认证路径
_PUBLIC_PATHS = {"/api/health", "/api/auth/login", "/docs", "/openapi.json", "/redoc"}

# 添加认证中间件
app.middleware("http")(create_auth_middleware(_PUBLIC_PATHS))

# 注册各模块路由
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(vector_store_router)
app.include_router(models_router)
app.include_router(chat_router)
app.include_router(system_router)


@app.on_event("startup")
async def startup_event():
    app.state.runtime_registry = RuntimeRegistry()
    # 初始化认证模块
    init_auth(Config.AUTH_PASSWORD)
    # 加载加密的 API Keys
    Config._load_encrypted_keys()
    # 后台模型预热
    schedule_background_preload(app.state.runtime_registry)
