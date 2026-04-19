"""Persistent IP-state cache — avoids unnecessary API calls when the IP is unchanged."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IPState:
    """Last observed public IPs."""

    ipv4: str | None = None
    ipv6: str | None = None


class StateStore:
    """Atomic JSON-backed state store at ``<state_dir>/state.json`` with 0600 perms."""

    def __init__(self, state_dir: Path) -> None:
        self._path = Path(state_dir) / "state.json"
        self._dir = Path(state_dir)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> IPState:
        if not self._path.is_file():
            return IPState()
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("state unreadable at %s, resetting: %s", self._path, exc)
            return IPState()
        if not isinstance(data, dict):
            return IPState()
        v4 = data.get("ipv4")
        v6 = data.get("ipv6")
        return IPState(
            ipv4=v4 if isinstance(v4, str) else None,
            ipv6=v6 if isinstance(v6, str) else None,
        )

    def save(self, state: IPState) -> None:
        try:
            self._dir.mkdir(parents=True, exist_ok=True, mode=0o750)
        except OSError as exc:
            log.warning("cannot create state dir %s: %s", self._dir, exc)
            return

        payload = json.dumps(asdict(state), separators=(",", ":"))
        try:
            fd, tmp_name = tempfile.mkstemp(prefix=".state-", suffix=".json", dir=str(self._dir))
            tmp = Path(tmp_name)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(payload)
                    f.flush()
                    os.fsync(f.fileno())
                tmp.chmod(0o600)
                tmp.replace(self._path)
            except OSError:
                tmp.unlink(missing_ok=True)
                raise
        except OSError as exc:
            log.warning("cannot persist state to %s: %s", self._path, exc)
