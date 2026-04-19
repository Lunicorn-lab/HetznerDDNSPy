"""Tests for CLI glue."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from hetzner_ddns.cli import main
from hetzner_ddns.updater import RunResult


@pytest.fixture
def good_config_file(tmp_path: Path) -> Path:
    p = tmp_path / "c.conf"
    p.write_text(
        "API_TOKEN=tok_cli_testtoken1234567890\n"
        "ZONE=example.com\n"
        'RECORDS="@"\n'
        "IPV4=true\nIPV6=false\n"
        f"STATE_DIR={tmp_path / 'state'}\n"
    )
    p.chmod(0o600)
    return p


class TestCLI:
    def test_check_config_ok(self, good_config_file: Path) -> None:
        with patch("hetzner_ddns.config.DEFAULT_CONFIG_PATHS", (good_config_file,)):
            assert main(["--check-config"]) == 0

    def test_missing_token_exits_config(self, tmp_path: Path) -> None:
        p = tmp_path / "c.conf"
        p.write_text("ZONE=example.com\n")
        with patch("hetzner_ddns.config.DEFAULT_CONFIG_PATHS", (p,)):
            rc = main(["--check-config"])
        assert rc == 2

    def test_daemon_exits_on_stop_flag(self, good_config_file: Path) -> None:
        with (
            patch("hetzner_ddns.config.DEFAULT_CONFIG_PATHS", (good_config_file,)),
            patch(
                "hetzner_ddns.cli.run_once",
                return_value=RunResult(None, None, False, 0, 0, 0, 0, False),
            ),
            patch("hetzner_ddns.cli.time.sleep") as sleep_mock,
            patch("hetzner_ddns.cli._setup_signals") as setup_sig,
        ):
            # Simulate a SIGTERM being delivered during the first sleep.
            stop_flag_ref: list[list[bool]] = []

            def capture(flag: list[bool]) -> None:
                stop_flag_ref.append(flag)

            setup_sig.side_effect = capture

            def set_stop(*_a: object, **_kw: object) -> None:
                stop_flag_ref[0][0] = True

            sleep_mock.side_effect = set_stop
            rc = main(["--daemon"])
        assert rc == 0

    def test_log_level_override(self, good_config_file: Path) -> None:
        with patch("hetzner_ddns.config.DEFAULT_CONFIG_PATHS", (good_config_file,)):
            assert main(["--check-config", "--log-level", "DEBUG"]) == 0
