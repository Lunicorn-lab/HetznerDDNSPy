"""Error paths in the state store."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from hetzner_ddns.state import IPState, StateStore


class TestStateErrors:
    def test_save_swallows_mkdir_failure(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path / "x")
        with patch("hetzner_ddns.state.Path.mkdir", side_effect=OSError("denied")):
            store.save(IPState(ipv4="1.2.3.4"))
        # No exception raised — operation is best-effort.

    def test_save_swallows_write_failure(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path)
        with patch("hetzner_ddns.state.tempfile.mkstemp", side_effect=OSError("disk full")):
            store.save(IPState(ipv4="1.2.3.4"))

    def test_load_handles_unreadable(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path)
        store.path.write_text('{"ipv4": 123}')  # wrong type
        # types are coerced / ignored — should fall back to None
        state = store.load()
        assert state.ipv4 is None
