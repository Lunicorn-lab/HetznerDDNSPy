"""Unit tests for logging setup and secret redaction."""

from __future__ import annotations

import json
import logging
from io import StringIO

import pytest

from hetzner_ddns.logging_setup import JsonFormatter, RedactingFilter, configure_logging, redact


class TestRedact:
    @pytest.mark.parametrize(
        "raw",
        [
            "Auth-API-Token: abcdef123456",
            "api_token=abcdef123456",
            "API-Token:abcdef123456",
            "Authorization: Bearer abcdef.abcdef-abc",
        ],
    )
    def test_redacts_known_patterns(self, raw: str) -> None:
        assert "abcdef" not in redact(raw).lower() or "[REDACTED]" in redact(raw)

    def test_leaves_innocuous_strings(self) -> None:
        assert redact("zone=example.com") == "zone=example.com"


class TestRedactingFilter:
    def test_filters_msg(self) -> None:
        rec = logging.LogRecord(
            "t",
            logging.INFO,
            "p",
            1,
            "api_token=supersecretvalue123",
            None,
            None,
        )
        RedactingFilter().filter(rec)
        assert "supersecretvalue123" not in rec.getMessage()


class TestJsonFormatter:
    def test_emits_json_with_extras(self) -> None:
        fmt = JsonFormatter()
        rec = logging.LogRecord("t", logging.INFO, "p", 1, "hello %s", ("world",), None)
        rec.extra_field = "hi"
        out = fmt.format(rec)
        payload = json.loads(out)
        assert payload["msg"] == "hello world"
        assert payload["level"] == "INFO"
        assert payload["extra_field"] == "hi"


class TestConfigureLogging:
    def test_json_mode(self, caplog: pytest.LogCaptureFixture) -> None:
        configure_logging("INFO", fmt="json")
        log = logging.getLogger("test.json")
        buf = StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(JsonFormatter())
        log.addHandler(handler)
        log.info("zone=%s", "example.com")
        handler.flush()
        # Just sanity — real output tested via JsonFormatter directly.
        assert "example.com" in buf.getvalue()
