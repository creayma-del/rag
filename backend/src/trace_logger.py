import json
import logging
import uuid


LOGGER_NAME = "rag.pipeline"


def get_pipeline_logger():
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def new_trace_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def log_pipeline(trace_id, chain, stage, message, **details):
    payload = {
        "trace_id": trace_id,
        "chain": chain,
        "stage": stage,
        "message": message,
    }
    if details:
        payload["details"] = details

    get_pipeline_logger().info(json.dumps(payload, ensure_ascii=False, default=str))
