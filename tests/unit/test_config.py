"""Unit tests for configuration loading."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from hetzner_ddns.config import fetch_token_from_op, load_config, load_env_file
from hetzner_ddns.errors import ConfigError


class TestLoadEnvFile:
    def test_simple(self, tmp_path: Path) -> None:
        p = tmp_path / "c.conf"
        p.write_text('API_TOKEN="abcdef"\nZONE=example.com\n# comment\nIPV4=true\n')
        assert load_env_file(p) == {
            "API_TOKEN": "abcdef",
            "ZONE": "example.com",
            "IPV4": "true",
        }

    def test_strip_single_quotes_and_export(self, tmp_path: Path) -> None:
        p = tmp_path / "c.conf"
        p.write_text("export API_TOKEN='secret'\nZONE=example.com\n")
        cfg = load_env_file(p)
        assert cfg["API_TOKEN"] == "secret"
        assert cfg["ZONE"] == "example.com"

    def test_missing_file(self, tmp_path: Path) -> None:
        assert load_env_file(tmp_path / "missing.conf") == {}

    def test_ignores_unknown_keys(self, tmp_path: Path) -> None:
        p = tmp_path / "c.conf"
        p.write_text("FOO=bar\nAPI_TOKEN=x\n")
        assert "FOO" not in load_env_file(p)


class TestLoadConfig:
    def _good_file(self, tmp_path: Path) -> Path:
        p = tmp_path / "c.conf"
        p.write_text(
            'API_TOKEN="tok_abcdefghij0123456789"\n'
            "ZONE=example.com\n"
            'RECORDS="@ www vpn"\n'
            "IPV4=true\nIPV6=false\nINTERVAL=60\nTTL=300\n"
        )
        return p

    def test_load_from_file(self, tmp_path: Path) -> None:
        cfg = load_config(env={}, config_paths=(self._good_file(tmp_path),), op_lookup=False)
        assert cfg.zone == "example.com"
        assert cfg.records == ("@", "www", "vpn")
        assert cfg.ipv6_enabled is False
        assert cfg.interval == 60
        assert cfg.ttl == 300

    def test_env_overrides_file(self, tmp_path: Path) -> None:
        cfg = load_config(
            env={"ZONE": "other.com", "API_TOKEN": "tok_anotherone12345678"},
            config_paths=(self._good_file(tmp_path),),
            op_lookup=False,
        )
        assert cfg.zone == "other.com"
        assert cfg.api_token == "tok_anotherone12345678"

    def test_missing_token_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "c.conf"
        p.write_text("ZONE=example.com\n")
        with pytest.raises(ConfigError, match="API_TOKEN"):
            load_config(env={}, config_paths=(p,), op_lookup=False)

    def test_short_token_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "c.conf"
        p.write_text("API_TOKEN=short\nZONE=example.com\n")
        with pytest.raises(ConfigError, match="malformed"):
            load_config(env={}, config_paths=(p,), op_lookup=False)

    def test_missing_zone_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "c.conf"
        p.write_text("API_TOKEN=tok_abcdefghij0123456789\n")
        with pytest.raises(ConfigError, match="ZONE"):
            load_config(env={}, config_paths=(p,), op_lookup=False)

    def test_both_disabled_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "c.conf"
        p.write_text(
            "API_TOKEN=tok_abcdefghij0123456789\nZONE=example.com\nIPV4=false\nIPV6=false\n"
        )
        with pytest.raises(ConfigError, match="IPV4/IPV6"):
            load_config(env={}, config_paths=(p,), op_lookup=False)

    def test_invalid_bool_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "c.conf"
        p.write_text("API_TOKEN=tok_abcdefghij0123456789\nZONE=example.com\nIPV4=maybe\n")
        with pytest.raises(ConfigError, match="IPV4"):
            load_config(env={}, config_paths=(p,), op_lookup=False)

    def test_invalid_log_level(self, tmp_path: Path) -> None:
        p = tmp_path / "c.conf"
        p.write_text("API_TOKEN=tok_abcdefghij0123456789\nZONE=example.com\nLOG_LEVEL=BOGUS\n")
        with pytest.raises(ConfigError, match="LOG_LEVEL"):
            load_config(env={}, config_paths=(p,), op_lookup=False)

    def test_op_fallback_invoked(self, tmp_path: Path) -> None:
        p = tmp_path / "c.conf"
        p.write_text("ZONE=example.com\n")
        with patch(
            "hetzner_ddns.config.fetch_token_from_op",
            return_value="tok_from_op_1234567890",
        ):
            cfg = load_config(env={}, config_paths=(p,), op_lookup=True)
        assert cfg.api_token == "tok_from_op_1234567890"
        assert cfg._token_source == "1password-cli"


class TestFetchTokenFromOp:
    def test_no_op_binary_returns_none(self) -> None:
        with patch("hetzner_ddns.config.shutil.which", return_value=None):
            assert fetch_token_from_op() is None
