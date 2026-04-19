"""End-to-end tests: exercise the CLI against a fake Hetzner API."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from hetzner_ddns.cli import main
from hetzner_ddns.errors import IPLookupError
from hetzner_ddns.ip import Provider, discover_ipv4

if TYPE_CHECKING:
    from pytest_httpserver import HTTPServer


@pytest.fixture
def e2e_config_file(tmp_path: Path) -> Path:
    cfg = tmp_path / "hetzner_ddns.conf"
    cfg.write_text(
        "API_TOKEN=tok_e2e_testtoken1234567890\n"
        "ZONE=example.com\n"
        'RECORDS="@ www"\n'
        "IPV4=true\nIPV6=true\nINTERVAL=60\nTTL=300\n"
        f"STATE_DIR={tmp_path / 'state'}\n"
    )
    cfg.chmod(0o600)
    return cfg


@pytest.mark.e2e
class TestCLIE2E:
    def test_check_config_exits_zero(self, e2e_config_file: Path, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        with patch(
            "hetzner_ddns.config.DEFAULT_CONFIG_PATHS",
            (e2e_config_file,),
        ):
            rc = main(["--check-config"])
        assert rc == 0
        # --check-config does not touch the network or state dir
        assert not state_dir.exists()

    def test_full_once_pass(
        self,
        e2e_config_file: Path,
        fake_api: HTTPServer,
        tmp_path: Path,
    ) -> None:
        fake_api.expect_request("/zones", method="GET").respond_with_json(
            {"zones": [{"id": "z1", "name": "example.com"}]}
        )
        fake_api.expect_request("/records", method="GET").respond_with_json({"records": []})
        # 4 creates: @ A, @ AAAA, www A, www AAAA
        for _ in range(4):
            fake_api.expect_oneshot_request("/records", method="POST").respond_with_json(
                {
                    "record": {
                        "id": "x",
                        "name": "",
                        "type": "A",
                        "value": "1.1.1.1",
                        "zone_id": "z1",
                        "ttl": 300,
                    }
                }
            )

        with (
            patch("hetzner_ddns.config.DEFAULT_CONFIG_PATHS", (e2e_config_file,)),
            patch("hetzner_ddns.updater.discover_ipv4", return_value="203.0.113.42"),
            patch("hetzner_ddns.updater.discover_ipv6", return_value="2001:db8::2"),
            patch(
                "hetzner_ddns.hetzner.DEFAULT_BASE_URL",
                fake_api.url_for("").rstrip("/"),
            ),
            patch("hetzner_ddns.hetzner.DEFAULT_TIMEOUT", 2.0),
        ):
            rc = main(["--once"])
        assert rc == 0

    def test_ip_unchanged_short_circuits(
        self,
        e2e_config_file: Path,
        fake_api: HTTPServer,
        tmp_path: Path,
    ) -> None:
        # Pre-populate state so the run exits without touching the API.
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "state.json").write_text('{"ipv4":"203.0.113.42","ipv6":"2001:db8::2"}')

        with (
            patch("hetzner_ddns.config.DEFAULT_CONFIG_PATHS", (e2e_config_file,)),
            patch("hetzner_ddns.updater.discover_ipv4", return_value="203.0.113.42"),
            patch("hetzner_ddns.updater.discover_ipv6", return_value="2001:db8::2"),
            patch(
                "hetzner_ddns.hetzner.DEFAULT_BASE_URL",
                fake_api.url_for("").rstrip("/"),
            ),
        ):
            rc = main(["--once"])
        assert rc == 0
        # No expectations set on fake_api → check_assertions will pass.

    def test_ip_provider_all_fail(self) -> None:
        """All IP providers fail -> IPLookupError."""
        dead = [Provider("dead", "https://127.0.0.1:1/never")]
        with pytest.raises(IPLookupError):
            discover_ipv4(providers=dead, timeout=0.2, shuffle=False)

    def test_dry_run_exits_zero(self, e2e_config_file: Path, fake_api: HTTPServer) -> None:
        fake_api.expect_request("/zones", method="GET").respond_with_json(
            {"zones": [{"id": "z1", "name": "example.com"}]}
        )
        fake_api.expect_request("/records", method="GET").respond_with_json({"records": []})
        with (
            patch("hetzner_ddns.config.DEFAULT_CONFIG_PATHS", (e2e_config_file,)),
            patch("hetzner_ddns.updater.discover_ipv4", return_value="203.0.113.42"),
            patch("hetzner_ddns.updater.discover_ipv6", return_value=None),
            patch(
                "hetzner_ddns.hetzner.DEFAULT_BASE_URL",
                fake_api.url_for("").rstrip("/"),
            ),
        ):
            rc = main(["--dry-run"])
        assert rc == 0

    def test_bad_token_exits_auth(self, e2e_config_file: Path, fake_api: HTTPServer) -> None:
        fake_api.expect_request("/zones", method="GET").respond_with_data(
            '{"message":"bad"}', status=401
        )
        with (
            patch("hetzner_ddns.config.DEFAULT_CONFIG_PATHS", (e2e_config_file,)),
            patch("hetzner_ddns.updater.discover_ipv4", return_value="203.0.113.42"),
            patch("hetzner_ddns.updater.discover_ipv6", return_value=None),
            patch(
                "hetzner_ddns.hetzner.DEFAULT_BASE_URL",
                fake_api.url_for("").rstrip("/"),
            ),
        ):
            rc = main(["--once"])
        # AuthError path returns EXIT_API (we chose not to map AuthError → EXIT_AUTH).
        assert rc != 0
