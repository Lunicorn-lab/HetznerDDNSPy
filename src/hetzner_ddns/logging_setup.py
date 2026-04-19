# SPDX-License-Identifier: GPL-3.0-or-later
"""Logging setup with secret redaction and optional JSON output."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from typing import Any, Final

_SECRET_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"(Auth-API-Token\s*[:=]\s*)([^\s,}\"']+)", re.IGNORECASE),
    re.compile(r"(api[_-]?token\s*[:=]\s*)([^\s,}\"']+)", re.IGNORECASE),
    re.compile(r"(bearer\s+)([A-Za-z0-9._\-]+)", re.IGNORECASE),
)
_REDACTED: Final[str] = "[REDACTED]"


def redact(value: str) -> str:
    """Replace known secret patterns in a string."""
    for pat in _SECRET_PATTERNS:
        value = pat.sub(lambda m: f"{m.group(1)}{_REDACTED}", value)
    return value


class RedactingFilter(logging.Filter):
    """Redact secrets from every log record before it is emitted."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if record.args:
            record.args = tuple(redact(str(a)) if isinstance(a, str) else a for a in record.args)
        return True


class JsonFormatter(logging.Formatter):
    """Minimal structured JSON formatter (stdlib-only)."""

    _RESERVED: Final[frozenset[str]] = frozenset(
        {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "message",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
            "taskName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key, val in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                payload[key] = val
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO", *, fmt: str | None = None) -> None:
    """Configure root logging.

    Args:
        level: Log level name (``DEBUG``, ``INFO``, ...).
        fmt: ``json`` for JSON output; anything else (or ``None``) uses text.
    """
    fmt = fmt or os.environ.get("LOG_FORMAT", "text")
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.addFilter(RedactingFilter())
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    logging.getLogger("urllib3").setLevel(logging.WARNING)
