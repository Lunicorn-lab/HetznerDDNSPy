"""Tests for the 1Password CLI fallback in config."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import patch

from hetzner_ddns.config import fetch_token_from_op


def _completed(stdout: str = "", returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)


class TestFetchTokenFromOp:
    def test_raw_path_happy(self) -> None:
        with (
            patch("hetzner_ddns.config.shutil.which", return_value="/usr/bin/op"),
            patch(
                "hetzner_ddns.config.subprocess.run",
                return_value=_completed(stdout="tok_from_op_xxxxxxxxxxxx\n"),
            ),
        ):
            assert fetch_token_from_op() == "tok_from_op_xxxxxxxxxxxx"

    def test_raw_fails_then_json_fallback(self) -> None:
        calls: list[object] = []

        def fake_run(*args: object, **_kw: object) -> SimpleNamespace:
            calls.append(args)
            if len(calls) == 1:
                return _completed(returncode=1)
            return _completed(
                stdout='{"fields":[{"label":"API_TOKEN","value":"tok_json_1234567890abc"}]}'
            )

        with (
            patch("hetzner_ddns.config.shutil.which", return_value="/usr/bin/op"),
            patch("hetzner_ddns.config.subprocess.run", side_effect=fake_run),
        ):
            assert fetch_token_from_op() == "tok_json_1234567890abc"

    def test_timeout_returns_none(self) -> None:
        def boom(*_a: object, **_kw: object) -> None:
            raise subprocess.TimeoutExpired(cmd="op", timeout=1)

        with (
            patch("hetzner_ddns.config.shutil.which", return_value="/usr/bin/op"),
            patch("hetzner_ddns.config.subprocess.run", side_effect=boom),
        ):
            assert fetch_token_from_op() is None

    def test_oserror_returns_none(self) -> None:
        with (
            patch("hetzner_ddns.config.shutil.which", return_value="/usr/bin/op"),
            patch("hetzner_ddns.config.subprocess.run", side_effect=OSError("x")),
        ):
            assert fetch_token_from_op() is None

    def test_json_no_matching_field(self) -> None:
        responses = [
            _completed(returncode=1),
            _completed(stdout='{"fields":[{"label":"OTHER","value":"x"}]}'),
        ]
        with (
            patch("hetzner_ddns.config.shutil.which", return_value="/usr/bin/op"),
            patch("hetzner_ddns.config.subprocess.run", side_effect=responses),
        ):
            assert fetch_token_from_op() is None

    def test_invalid_json_returns_none(self) -> None:
        responses = [
            _completed(returncode=1),
            _completed(stdout="not json"),
        ]
        with (
            patch("hetzner_ddns.config.shutil.which", return_value="/usr/bin/op"),
            patch("hetzner_ddns.config.subprocess.run", side_effect=responses),
        ):
            assert fetch_token_from_op() is None
