"""App-level logging with loguru.

One sink on stderr, level from ``LOG_LEVEL`` (default INFO). Databricks Apps captures it into the App logs
(`databricks apps logs <app>`) and, with App telemetry on, exports it to the Unity Catalog ``*_otel_logs``
table. Standard-library loggers (uvicorn, the Databricks SDK, agentkit, MLflow, httpx) are intercepted so
every line has one format; chatty client libraries are capped at WARNING unless ``LOG_LEVEL=DEBUG``.
"""

from __future__ import annotations

import inspect
import logging
import os
import sys

from loguru import logger

_NOISY: tuple[str, ...] = ("httpx", "httpcore", "urllib3", "databricks.sdk", "mlflow", "py4j")


class InterceptHandler(logging.Handler):
    """Route standard-library log records to loguru, preserving level and caller."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame, depth = frame.f_back, depth + 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def configure_logging() -> None:
    level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        backtrace=False,
        diagnose=False,  # never dump local variables (tokens, secrets) into App logs
    )
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        logging.getLogger(name).handlers = [InterceptHandler()]
        logging.getLogger(name).propagate = False
    if level != "DEBUG":
        for name in _NOISY:
            logging.getLogger(name).setLevel(logging.WARNING)
    logger.info("Logging configured at {}", level)
