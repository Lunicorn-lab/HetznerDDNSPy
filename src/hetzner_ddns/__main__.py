"""Module entry point: ``python -m hetzner_ddns``."""

from __future__ import annotations

from hetzner_ddns.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
