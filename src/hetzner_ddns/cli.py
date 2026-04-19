# SPDX-License-Identifier: GPL-3.0-or-later
"""Command-line entry point."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from collections.abc import Sequence
from typing import Final

from hetzner_ddns import __version__
from hetzner_ddns.config import load_config
from hetzner_ddns.errors import ConfigError, HetznerDDNSError
from hetzner_ddns.hetzner import HetznerDNSClient
from hetzner_ddns.logging_setup import configure_logging
from hetzner_ddns.state import StateStore
from hetzner_ddns.updater import run_once

log = logging.getLogger("hetzner_ddns")

EXIT_OK: Final[int] = 0
EXIT_CONFIG: Final[int] = 2
EXIT_AUTH: Final[int] = 3
EXIT_API: Final[int] = 4
EXIT_INTERRUPTED: Final[int] = 130


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hetzner-ddns",
        description="Update Hetzner DNS A/AAAA records with this host's public IP.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--once",
        action="store_true",
        help="Run one reconciliation pass and exit (default; ideal for systemd timers).",
    )
    mode.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuously in a loop with the configured INTERVAL.",
    )
    mode.add_argument(
        "--check-config",
        action="store_true",
        help="Validate the configuration and exit without hitting any network.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do everything but never mutate Hetzner — useful for verification.",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Override LOG_LEVEL from config/env.",
    )
    parser.add_argument(
        "--log-format",
        default=None,
        choices=["text", "json"],
        help="Override LOG_FORMAT from config/env.",
    )
    return parser


def _setup_signals(stop_flag: list[bool]) -> None:
    def _handler(signum: int, _frame: object) -> None:
        log.info("signal %d received — shutting down after current iteration", signum)
        stop_flag[0] = True

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        config = load_config()
    except ConfigError as exc:
        configure_logging("ERROR", fmt=args.log_format or "text")
        log.error("configuration error: %s", exc)  # noqa: TRY400 — user-facing error, no traceback
        return EXIT_CONFIG

    configure_logging(
        args.log_level or config.log_level,
        fmt=args.log_format or config.log_format,
    )
    log.info("hetzner-ddns %s starting", __version__)
    # Stringify the dict ourselves — logging unwraps a single mapping arg into
    # %-mapping mode, which trips on "%s" with no key.
    log.debug("config: %s", str(config.redacted()))

    if args.check_config:
        log.info("configuration OK")
        return EXIT_OK

    client = HetznerDNSClient(config.api_token)
    store = StateStore(config.state_dir)

    if args.daemon:
        return _run_daemon(config, client, store, dry_run=args.dry_run)
    return _run_once(config, client, store, dry_run=args.dry_run)


def _run_once(config, client, store, *, dry_run: bool) -> int:  # type: ignore[no-untyped-def]
    try:
        result = run_once(config, client=client, store=store, dry_run=dry_run)
    except HetznerDDNSError as exc:
        log.exception("run failed: %s", exc)  # noqa: TRY401 — we want the full traceback here
        return EXIT_API
    log.info(
        "done ipv4=%s ipv6=%s created=%d updated=%d skipped=%d dry_run=%s",
        result.ipv4,
        result.ipv6,
        result.created,
        result.updated,
        result.skipped,
        result.dry_run,
    )
    return EXIT_OK


def _run_daemon(config, client, store, *, dry_run: bool) -> int:  # type: ignore[no-untyped-def]
    stop_flag = [False]
    _setup_signals(stop_flag)
    log.info("daemon mode: interval=%ds", config.interval)
    while not stop_flag[0]:
        try:
            run_once(config, client=client, store=store, dry_run=dry_run)
        except HetznerDDNSError as exc:
            log.exception("iteration failed: %s", exc)  # noqa: TRY401 — daemon logs + continues
        # Sleep in small slices so SIGTERM is responsive.
        remaining = config.interval
        while remaining > 0 and not stop_flag[0]:
            slice_s = min(remaining, 1.0)
            time.sleep(slice_s)
            remaining -= slice_s
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
