"""共享依赖：跨模块公共函数和 FastAPI 依赖注入。"""

from fastapi import Request
from src.qa_engine import RuntimeRegistry


def get_runtime_registry(request: Request) -> RuntimeRegistry:
    """从 app.state 获取 RuntimeRegistry 实例（FastAPI 依赖注入）。"""
    runtime_registry = getattr(request.app.state, "runtime_registry", None)
    if runtime_registry is None:
        runtime_registry = RuntimeRegistry()
        request.app.state.runtime_registry = runtime_registry
    return runtime_registry
