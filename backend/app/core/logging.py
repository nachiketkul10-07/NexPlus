"""
Structured Logging Configuration with ContextVar support for Request correlation IDs.
"""
import logging
import sys
from contextvars import ContextVar
from typing import Optional

request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class RequestIdFormatter(logging.Formatter):
    """Log formatter that automatically attaches request_id if available."""
    def format(self, record: logging.LogRecord) -> str:
        req_id = request_id_ctx.get()
        record.request_id = f"[{req_id}]" if req_id else "[-]"
        return super().format(record)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configures application logger."""
    logger = logging.getLogger("pulseops")
    logger.setLevel(log_level.upper())
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    formatter = RequestIdFormatter(
        fmt="%(asctime)s | %(levelname)-7s | %(request_id)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


logger = setup_logging()
