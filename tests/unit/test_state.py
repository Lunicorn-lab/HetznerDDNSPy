"""Unit tests for the state store."""

from __future__ import annotations

import stat
from pathlib import Path

from hetzner_ddns.state import IPState, StateStore


class TestStateStore:
    def test_empty_when_missing(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path)
        assert store.load() == IPState()

    def test_roundtrip(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path)
        store.save(IPState(ipv4="1.2.3.4", ipv6="2001:db8::1"))
        assert store.load() == IPState(ipv4="1.2.3.4", ipv6="2001:db8::1")

    def test_file_mode_is_0600(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path)
        store.save(IPState(ipv4="1.2.3.4"))
        mode = stat.S_IMODE(store.path.stat().st_mode)
        assert mode == 0o600

    def test_corrupt_resets(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path)
        store.save(IPState(ipv4="1.2.3.4"))
        store.path.write_text("NOT JSON")
        assert store.load() == IPState()

    def test_non_dict_payload_resets(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path)
        store.save(IPState(ipv4="1.2.3.4"))
        store.path.write_text('["array","payload"]')
        assert store.load() == IPState()
