import json
import logging
import sys
from typing import Any


def get_logger(name: str) -> logging.Logger:
    """Return a console logger."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    logger.propagate = False
    return logger


def log_job_event(
    job_id: str,
    step: str,
    status: str,
    message: str | None = None,
    error_code: str | None = None,
    extra: dict[str, Any] | None = None,
    logger: logging.Logger | None = None,
) -> None:
    """Log a structured job event to console."""
    logger = logger or get_logger("browser-worker")
    payload: dict[str, Any] = {
        "job_id": job_id,
        "step": step,
        "status": status,
        "message": message,
        "error_code": error_code,
        "extra": extra,
    }
    logger.info(json.dumps(payload, ensure_ascii=False))
