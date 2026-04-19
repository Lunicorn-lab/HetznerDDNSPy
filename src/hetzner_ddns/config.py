# SPDX-License-Identifier: GPL-3.0-or-later
"""Configuration loading with strict precedence and validation.

Precedence (highest wins):
    1. Environment variables
    2. Config file (``/usr/local/etc/hetzner_ddns.conf`` or ``/etc/hetzner_ddns.conf``)
    3. 1Password CLI (``op``) — only for ``API_TOKEN``
    4. Hard-coded defaults
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from hetzner_ddns.errors import ConfigError
from hetzner_ddns.validation import (
    validate_interval,
    validate_record_name,
    validate_ttl,
    validate_zone,
)

log = logging.getLogger(__name__)

DEFAULT_CONFIG_PATHS: Final[tuple[Path, ...]] = (
    Path("/usr/local/etc/hetzner_ddns.conf"),
    Path("/etc/hetzner_ddns.conf"),
)
DEFAULT_INTERVAL: Final[int] = 300
DEFAULT_TTL: Final[int] = 300
DEFAULT_STATE_DIR: Final[Path] = Path("/var/lib/hetzner_ddns")
OP_ITEM_TITLE: Final[str] = "Hetzner DDNS"
OP_FIELD: Final[str] = "API_TOKEN"
OP_TIMEOUT_SEC: Final[float] = 15.0

_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSY: Final[frozenset[str]] = frozenset({"0", "false", "no", "off", ""})
_KNOWN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "API_TOKEN",
        "ZONE",
        "RECORDS",
        "IPV4",
        "IPV6",
        "INTERVAL",
        "TTL",
        "LOG_LEVEL",
        "LOG_FORMAT",
        "STATE_DIR",
    }
)


@dataclass(frozen=True, slots=True)
class Config:
    """Validated runtime configuration."""

    api_token: str
    zone: str
    records: tuple[str, ...]
    ipv4_enabled: bool
    ipv6_enabled: bool
    interval: int
    ttl: int
    state_dir: Path
    log_level: str = "INFO"
    log_format: str = "text"
    _token_source: str = field(default="unknown", repr=False)

    def redacted(self) -> dict[str, object]:
        """Dict form with the token redacted — safe to log."""
        return {
            "zone": self.zone,
            "records": list(self.records),
            "ipv4_enabled": self.ipv4_enabled,
            "ipv6_enabled": self.ipv6_enabled,
            "interval": self.interval,
            "ttl": self.ttl,
            "state_dir": str(self.state_dir),
            "log_level": self.log_level,
            "log_format": self.log_format,
            "token_source": self._token_source,
        }


def _parse_bool(value: str, *, key: str) -> bool:
    norm = value.strip().lower()
    if norm in _TRUTHY:
        return True
    if norm in _FALSY:
        return False
    raise ConfigError(f"{key} must be boolean-like, got {value!r}")


def load_env_file(path: Path) -> dict[str, str]:
    """Parse a ``KEY=VALUE`` file (simple, shell-compatible). Unknown keys are ignored."""
    env: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return env
    except OSError as exc:
        raise ConfigError(f"Cannot read config file {path}: {exc}") from exc

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            log.warning("config %s:%d skipped (no '='): %r", path, lineno, raw)
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        if key in _KNOWN_KEYS:
            env[key] = value
        else:
            log.warning("config %s:%d unknown key %r — ignored", path, lineno, key)
    return env


def fetch_token_from_op(  # noqa: PLR0911 — early-returns keep the happy path readable
    *,
    item: str = OP_ITEM_TITLE,
    field_name: str = OP_FIELD,
    op_binary: str | None = None,
) -> str | None:
    """Fetch ``API_TOKEN`` via the 1Password CLI. Returns ``None`` on any failure."""
    binary = op_binary or shutil.which("op")
    if not binary:
        log.debug("1Password CLI (op) not found on PATH")
        return None

    argv: list[str] = [binary, "item", "get", item, "--fields", field_name, "--reveal"]
    try:
        result = subprocess.run(  # noqa: S603 — fixed argv, no shell
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=OP_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        log.warning("1Password CLI timed out after %.1fs", OP_TIMEOUT_SEC)
        return None
    except OSError as exc:
        log.warning("1Password CLI exec failed: %s", exc)
        return None

    if result.returncode == 0:
        token = result.stdout.strip()
        if token:
            return token

    # Fallback: JSON output
    try:
        result = subprocess.run(  # noqa: S603
            [binary, "item", "get", item, "--format", "json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=OP_TIMEOUT_SEC,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.warning("1Password CLI fallback failed: %s", exc)
        return None

    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    for f in data.get("fields", []):
        if (
            f.get("label", "").upper() == field_name.upper()
            or f.get("id", "").upper() == field_name.upper()
        ):
            val = f.get("value")
            if isinstance(val, str) and val.strip():
                return val.strip()
    return None


def _pick_config_path(paths: tuple[Path, ...]) -> Path | None:
    for p in paths:
        if p.is_file():
            return p
    return None


def load_config(  # noqa: PLR0912 — validation of many config keys; splitting hurts readability
    *,
    env: dict[str, str] | None = None,
    config_paths: tuple[Path, ...] | None = None,
    op_lookup: bool | None = None,
) -> Config:
    """Build a validated :class:`Config`.

    Args:
        env: Environment overlay (defaults to :data:`os.environ`).
        config_paths: Candidate config files, first hit wins. If ``None``,
            :data:`DEFAULT_CONFIG_PATHS` is resolved at call time so tests
            can patch the module attribute.
        op_lookup: If ``True``, query 1Password when token missing. If
            ``None``, uses ``HETZNER_DDNS_DISABLE_OP`` env var as kill-switch.

    Raises:
        ConfigError: If required fields are missing or invalid.
    """
    env = dict(os.environ if env is None else env)
    if config_paths is None:
        config_paths = DEFAULT_CONFIG_PATHS
    if op_lookup is None:
        op_lookup = env.get("HETZNER_DDNS_DISABLE_OP", "").lower() not in _TRUTHY

    merged: dict[str, str] = {}
    chosen_path = _pick_config_path(config_paths)
    if chosen_path is not None:
        log.info("loading config from %s", chosen_path)
        merged.update(load_env_file(chosen_path))

    for k in _KNOWN_KEYS:
        if k in env:
            merged[k] = env[k]

    token = merged.get("API_TOKEN", "").strip()
    token_source = "config-file-or-env"  # noqa: S105 — label, not a secret
    if not token and op_lookup:
        op_token = fetch_token_from_op()
        if op_token:
            token = op_token
            token_source = "1password-cli"  # noqa: S105 — label, not a secret
    if not token:
        raise ConfigError(
            "API_TOKEN missing — set it in the config file, the environment, or 1Password."
        )
    if len(token) < 16 or any(c.isspace() for c in token):
        raise ConfigError("API_TOKEN looks malformed (too short or contains whitespace)")

    zone_raw = merged.get("ZONE", "").strip()
    if not zone_raw:
        raise ConfigError("ZONE is required")
    zone = validate_zone(zone_raw)

    records_raw = merged.get("RECORDS", "@").split()
    if not records_raw:
        raise ConfigError("RECORDS must contain at least one entry (use '@' for apex)")
    records = tuple(validate_record_name(r) for r in records_raw)

    ipv4 = _parse_bool(merged.get("IPV4", "true"), key="IPV4")
    ipv6 = _parse_bool(merged.get("IPV6", "true"), key="IPV6")
    if not (ipv4 or ipv6):
        raise ConfigError("At least one of IPV4/IPV6 must be enabled")

    try:
        interval = validate_interval(int(merged.get("INTERVAL", str(DEFAULT_INTERVAL))))
        ttl = validate_ttl(int(merged.get("TTL", str(DEFAULT_TTL))))
    except ValueError as exc:
        raise ConfigError(f"INTERVAL/TTL must be integers: {exc}") from exc

    log_level = merged.get("LOG_LEVEL", "INFO").upper()
    if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ConfigError(f"Invalid LOG_LEVEL: {log_level}")
    log_format = merged.get("LOG_FORMAT", "text").lower()
    if log_format not in {"text", "json"}:
        raise ConfigError(f"Invalid LOG_FORMAT: {log_format}")

    state_dir = Path(merged.get("STATE_DIR", str(DEFAULT_STATE_DIR)))

    return Config(
        api_token=token,
        zone=zone,
        records=records,
        ipv4_enabled=ipv4,
        ipv6_enabled=ipv6,
        interval=interval,
        ttl=ttl,
        state_dir=state_dir,
        log_level=log_level,
        log_format=log_format,
        _token_source=token_source,
    )
