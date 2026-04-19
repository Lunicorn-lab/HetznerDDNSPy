"""Shared pytest fixtures."""

from __future__ import annotations

import ssl
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from hetzner_ddns.config import Config
from hetzner_ddns.hetzner import HetznerDNSClient
from hetzner_ddns.state import StateStore

if TYPE_CHECKING:
    from pytest_httpserver import HTTPServer


@pytest.fixture
def tmp_state_dir(tmp_path: Path) -> Path:
    d = tmp_path / "state"
    d.mkdir()
    return d


@pytest.fixture
def state_store(tmp_state_dir: Path) -> StateStore:
    return StateStore(tmp_state_dir)


@pytest.fixture
def sample_config(tmp_state_dir: Path) -> Config:
    return Config(
        api_token="tok_abcdefghij0123456789",
        zone="example.com",
        records=("@", "www"),
        ipv4_enabled=True,
        ipv6_enabled=True,
        interval=300,
        ttl=300,
        state_dir=tmp_state_dir,
        log_level="INFO",
        log_format="text",
    )


@pytest.fixture
def insecure_ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


@pytest.fixture
def fake_api(httpserver: HTTPServer) -> Iterator[HTTPServer]:
    """Fake Hetzner API server listening on loopback HTTP (insecure, test-only)."""
    yield httpserver
    httpserver.check_assertions()


@pytest.fixture
def api_client(fake_api: HTTPServer) -> HetznerDNSClient:
    # Use zero sleep in retries so tests don't hang.
    return HetznerDNSClient(
        api_token="tok_testtoken1234567890",
        base_url=fake_api.url_for(""),
        timeout=2.0,
        max_retries=2,
        sleep=lambda _s: None,
    )
