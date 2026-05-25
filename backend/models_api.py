"""模型配置模块：模型列表、API Key 管理、模型预热。"""

import os
import threading
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config import Config
from src.auth import mask_value
from src.trace_logger import log_pipeline, new_trace_id
from dependencies import get_runtime_registry
from src.qa_engine import RuntimeRegistry

router = APIRouter(tags=["模型配置"])


# ---- 请求模型 ----

class ModelConfigRequest(BaseModel):
    model: str
    api_key: Optional[str] = None
    secret_key: Optional[str] = None


class PreloadRequest(BaseModel):
    model: str = Config.DEFAULT_MODEL
    use_reranker: bool = False


# ---- 预热工具函数 ----

def _start_preload_background(model: str, use_reranker: bool, runtime_registry: RuntimeRegistry):
    status = runtime_registry.get_llm_status(model)

    if status["state"] == "ready":
        return {"status": "ready", "model": model, "cached": True}

    if status["state"] == "loading":
        return {"status": "loading", "model": model}

    def load_in_background():
        try:
            runtime_registry.preload(
                model_name=model,
                use_reranker=use_reranker,
            )
        except Exception as e:
            print(f"后台预加载失败 [{model}]: {e}")

    threading.Thread(
        target=load_in_background,
        name=f"preload-bg-{model}",
        daemon=True,
    ).start()

    return {"status": "started", "model": model}


def schedule_background_preload(runtime_registry: RuntimeRegistry):
    """启动后台模型预热。"""
    if not Config.BACKGROUND_PRELOAD_ENABLED:
        return

    models_to_preload = tuple(
        model_name
        for model_name in Config.BACKGROUND_PRELOAD_MODELS
        if model_name in Config.MODEL_CONFIGS
    )
    if not models_to_preload:
        return

    def worker():
        delay_seconds = max(Config.BACKGROUND_PRELOAD_DELAY_SECONDS, 0)
        if delay_seconds:
            time.sleep(delay_seconds)

        for model_name in models_to_preload:
            trace_id = new_trace_id("bg-preload")
            log_pipeline(
                trace_id,
                "background_preload",
                "background_preload_start",
                "开始后台延迟预热本地模型",
                model=model_name,
                use_reranker=Config.BACKGROUND_PRELOAD_USE_RERANKER,
                delay_seconds=delay_seconds,
            )
            try:
                runtime_registry.preload(
                    model_name=model_name,
                    use_reranker=Config.BACKGROUND_PRELOAD_USE_RERANKER,
                )
                log_pipeline(
                    trace_id,
                    "background_preload",
                    "background_preload_complete",
                    "后台模型预热完成",
                    model=model_name,
                )
            except Exception as exc:
                log_pipeline(
                    trace_id,
                    "background_preload",
                    "background_preload_error",
                    "后台模型预热失败",
                    model=model_name,
                    error=str(exc),
                )

    threading.Thread(
        target=worker,
        name="rag-background-preload",
        daemon=True,
    ).start()


# ---- 路由 ----

@router.get("/api/models")
async def get_models():
    """获取可用模型列表。"""
    cloud_models = []
    local_models = []
    for name, config in Config.MODEL_CONFIGS.items():
        model_info = {
            "name": name,
            "model": config.get("model", ""),
            "description": config.get("description", config.get("model", ""))
        }
        if name.startswith("local"):
            local_models.append(model_info)
        else:
            cloud_models.append(model_info)
    return {
        "cloud_models": cloud_models,
        "local_models": local_models
    }


@router.get("/api/config/keys")
async def get_api_key_status():
    """返回各模型 API Key 的脱敏状态，不暴露明文。"""
    keys_status = {}
    for model_name, model_config in Config.MODEL_CONFIGS.items():
        if "api_key_env" not in model_config:
            continue
        masked = Config.get_model_api_key_masked(model_name)
        entry: dict = {
            "configured": bool(masked),
            "masked": masked,
        }
        secret_env_var = model_config.get("secret_key_env")
        if secret_env_var:
            secret_val = Config.get_env_value(secret_env_var)
            secret_configured = bool(secret_val) and not secret_val.lower().startswith(Config._PLACEHOLDER_PREFIX)
            entry["secret_configured"] = secret_configured
            if secret_configured:
                entry["secret_masked"] = mask_value(secret_val)
            else:
                entry["secret_masked"] = ""
        keys_status[model_name] = entry
    return {"keys": keys_status}


@router.post("/api/config")
async def update_config(
    request: ModelConfigRequest,
    runtime_registry: RuntimeRegistry = Depends(get_runtime_registry),
):
    """更新模型配置（API Key 等）。"""
    runtime_invalidated = False

    if request.api_key is not None:
        try:
            Config.set_model_api_key(request.model, request.api_key)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        runtime_invalidated = runtime_registry.invalidate_llm(request.model)

    if request.secret_key is not None:
        model_config = Config.get_model_config(request.model)
        if model_config and "secret_key_env" in model_config:
            secret_env_var = model_config["secret_key_env"]
            cleaned = request.secret_key.strip()
            os.environ[secret_env_var] = cleaned
            setattr(Config, secret_env_var, cleaned)
            Config._save_encrypted_keys()
            runtime_invalidated = runtime_invalidated or runtime_registry.invalidate_llm(request.model)

    return {
        "status": "success",
        "runtime_invalidated": runtime_invalidated,
    }


@router.get("/api/preload")
async def preload_models(
    model: str = Config.DEFAULT_MODEL,
    use_reranker: bool = False,
    runtime_registry: RuntimeRegistry = Depends(get_runtime_registry),
):
    """后台预热模型（GET）。"""
    return _start_preload_background(model=model, use_reranker=use_reranker, runtime_registry=runtime_registry)


@router.post("/api/preload")
async def preload_models_by_request(
    request: PreloadRequest,
    runtime_registry: RuntimeRegistry = Depends(get_runtime_registry),
):
    """后台预热模型（POST）。"""
    return _start_preload_background(
        model=request.model,
        use_reranker=request.use_reranker,
        runtime_registry=runtime_registry,
    )


@router.get("/api/preload/status")
async def preload_status(
    model: str = Config.DEFAULT_MODEL,
    runtime_registry: RuntimeRegistry = Depends(get_runtime_registry),
):
    """查询模型预热状态。"""
    status = runtime_registry.get_llm_status(model)
    return {
        "model": model,
        "state": status["state"],
        "cached": status["cached"],
        "error": status["error"],
    }
