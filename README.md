# HetznerDDNSPy

A **minimal, secure, stdlib-only** DynDNS updater for the [Hetzner DNS API](https://dns.hetzner.com/).
Runs as a hardened systemd timer, a distroless container, or both.

[![CI](https://github.com/Lunicorn/HetznerDDNSPy/actions/workflows/ci.yml/badge.svg)](https://github.com/Lunicorn/HetznerDDNSPy/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Lunicorn/HetznerDDNSPy/actions/workflows/codeql.yml/badge.svg)](https://github.com/Lunicorn/HetznerDDNSPy/actions/workflows/codeql.yml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/Lunicorn/HetznerDDNSPy/badge)](https://securityscorecards.dev/viewer/?uri=github.com/Lunicorn/HetznerDDNSPy)
[![PyPI](https://img.shields.io/pypi/v/hetzner-ddns.svg)](https://pypi.org/project/hetzner-ddns/)
[![Python](https://img.shields.io/pypi/pyversions/hetzner-ddns.svg)](https://pypi.org/project/hetzner-ddns/)
[![License: GPL v3+](https://img.shields.io/badge/License-GPLv3%2B-blue.svg)](LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-%E2%89%A590%25-brightgreen.svg)](#testing)

---

## Table of contents

- [Why](#why)
- [Features](#features)
- [Install](#install)
  - [Systemd (bare-metal)](#systemd-bare-metal)
  - [Docker / Compose](#docker--compose)
  - [PyPI](#pypi)
- [Configuration](#configuration)
- [Operating modes](#operating-modes)
- [Security](#security)
- [Development](#development)
- [Testing](#testing)
- [Project layout](#project-layout)
- [Documentation](#documentation)
- [License](#license)

---

## Why

Most DynDNS clients are either bloated, unmaintained, or ask you to install a
dependency tree you can't audit. `HetznerDDNSPy` is the opposite:

- **Zero runtime dependencies.** Everything the updater imports is CPython
  stdlib — no `requests`, no `httpx`, no shims. Auditable in an afternoon.
- **Hardened by default.** Systemd unit ships with `NoNewPrivileges`,
  `ProtectSystem=strict`, `SystemCallFilter=@system-service`, empty
  `CapabilityBoundingSet`, `MemoryDenyWriteExecute`, and more.
- **No surprises.** Reconciliation is a pure function; state lives in a single
  `0600` JSON file; a cached public-IP avoids hammering Hetzner's API.
- **Supply-chain signed.** Releases publish to PyPI via OIDC trusted
  publishing, images to GHCR with Sigstore cosign signatures and SLSA
  Level 3 provenance.

## Features

- Updates Hetzner **A and AAAA** records from the host's public IP.
- Pure-stdlib HTTP client with TLS 1.2+, full certificate verification,
  exponential backoff with jitter, and explicit 401/403/429/5xx handling.
- Public-IP discovery across multiple providers with automatic fallback.
- Token sourcing with strict precedence: **environment → config file → 1Password CLI**.
- Structured **JSON logs** (opt-in) with a redaction filter for tokens.
- `--once` (timer-friendly), `--daemon`, `--check-config`, `--dry-run` modes.
- Ships with:
  - a minimal, hardened **systemd** unit + timer,
  - a **distroless, non-root** container image,
  - an idempotent `install.sh` bootstrap script.
- CI runs Ruff, mypy `--strict`, pytest (≥ 90 % coverage), Bandit, Semgrep
  (OWASP ruleset), pip-audit, OSV Scanner, gitleaks, Trivy, Grype, hadolint,
  CodeQL, and OpenSSF Scorecard on every push.

## Install

### Systemd (bare-metal)

```bash
git clone https://github.com/Lunicorn/HetznerDDNSPy.git
cd HetznerDDNSPy
sudo ./install.sh
```

The installer:

1. creates a dedicated `hetzner-ddns` system user,
2. installs the package into an isolated `uv` virtualenv at `/opt/hetzner-ddns/venv`,
3. writes the config template to `/etc/hetzner_ddns.conf` (mode `0640`),
4. writes the state directory to `/var/lib/hetzner_ddns` (mode `0750`),
5. installs and validates the systemd unit + timer,
6. **does not** start the timer until you've filled in `API_TOKEN` and `ZONE`.

Then:

```bash
sudo $EDITOR /etc/hetzner_ddns.conf
sudo -u hetzner-ddns /opt/hetzner-ddns/venv/bin/hetzner-ddns --check-config
sudo systemctl enable --now hetzner_ddns.timer
systemctl list-timers hetzner_ddns.timer
journalctl -u hetzner_ddns.service -f
```

### Docker / Compose

```bash
docker run --rm \
  --read-only \
  --cap-drop=ALL \
  --security-opt=no-new-privileges:true \
  -e API_TOKEN=... \
  -e ZONE=example.com \
  -e RECORDS="@ www" \
  -v hetzner_ddns_state:/var/lib/hetzner_ddns \
  ghcr.io/lunicorn/hetznerddnspy:latest --once
```

Or with Compose (see [docker/docker-compose.yml](docker/docker-compose.yml)):

```bash
cd docker
cp ../etc/hetzner_ddns.conf.example .env   # fill in API_TOKEN, ZONE, RECORDS
docker compose up -d
```

The image is built from [`gcr.io/distroless/python3-debian12:nonroot`](https://github.com/GoogleContainerTools/distroless),
runs as UID `65532`, has no shell, and is cosign-signed on every release.
Verify with:

```bash
cosign verify ghcr.io/lunicorn/hetznerddnspy:vX.Y.Z \
  --certificate-identity-regexp='^https://github.com/Lunicorn/HetznerDDNSPy/' \
  --certificate-oidc-issuer=https://token.actions.githubusercontent.com
```

### PyPI

```bash
pipx install hetzner-ddns         # recommended: isolated env
# or
uv tool install hetzner-ddns
```

## Configuration

Configuration is resolved in this order (later wins):

1. 1Password CLI lookup (skipped when `HETZNER_DDNS_DISABLE_OP=1`),
2. `/etc/hetzner_ddns.conf` (or any path in `HETZNER_DDNS_CONFIG`),
3. Environment variables.

| Key                        | Required | Default                  | Notes                                                             |
|----------------------------|----------|--------------------------|-------------------------------------------------------------------|
| `API_TOKEN`                | yes      | —                        | Hetzner DNS API token. Never committed, never logged.             |
| `ZONE`                     | yes      | —                        | Apex domain, e.g. `example.com`.                                  |
| `RECORDS`                  | yes      | —                        | Space-separated labels. Use `@` for the apex.                     |
| `IPV4`                     | no       | `true`                   | Manage A records.                                                 |
| `IPV6`                     | no       | `true`                   | Manage AAAA records.                                              |
| `TTL`                      | no       | `300`                    | 60–86400.                                                         |
| `INTERVAL`                 | no       | `300`                    | Daemon-mode reconciliation interval (seconds).                    |
| `STATE_DIR`                | no       | `/var/lib/hetzner_ddns`  | Persists the last seen public IPs. Created at `0750`.             |
| `LOG_LEVEL`                | no       | `INFO`                   | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL`.              |
| `LOG_FORMAT`               | no       | `text`                   | `text` or `json` (structured, good for journald/Loki).            |
| `HETZNER_DDNS_DISABLE_OP`  | no       | unset                    | Set to `1` to skip the 1Password lookup.                          |

A documented example lives at [`etc/hetzner_ddns.conf.example`](etc/hetzner_ddns.conf.example).
For retrieving the token from 1Password, see [`1password_example.md`](1password_example.md).

## Operating modes

```text
hetzner-ddns --once            # one reconciliation pass — default, timer-friendly
hetzner-ddns --daemon          # long-running, honours INTERVAL; SIGTERM-aware
hetzner-ddns --check-config    # validate config, print redacted view, exit 0
hetzner-ddns --dry-run         # compute actions but never mutate Hetzner
hetzner-ddns --log-format json # structured logging to stdout
hetzner-ddns --version
```

Exit codes: `0` success, `2` config error, `3` auth error (401/403), `4` API
error, `130` interrupted.

The state cache means the tool only calls the Hetzner API when the public IP
actually changes — so a per-minute timer is cheap.

## Security

Security is a first-class concern, not an afterthought:

- **Hardened systemd unit** with `NoNewPrivileges`, `ProtectSystem=strict`,
  `ProtectHome`, `PrivateTmp`, `PrivateDevices`, `ProtectProc=invisible`,
  `ProcSubset=pid`, `RestrictNamespaces`, `RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX`,
  `RestrictRealtime`, `RestrictSUIDSGID`, `LockPersonality`,
  `MemoryDenyWriteExecute`, `SystemCallArchitectures=native`,
  `SystemCallFilter=@system-service ~@privileged @resources @mount @debug @reboot @swap @raw-io`,
  empty `CapabilityBoundingSet=` and `AmbientCapabilities=`, `UMask=0077`,
  `KeyringMode=private`, `RemoveIPC`, `MemoryMax=128M`, `TasksMax=32`,
  `CPUQuota=25%`.
- **Distroless, non-root container** (UID 65532), read-only root FS,
  `cap_drop: ALL`, `no-new-privileges`.
- **TLS verified** everywhere — `ssl.CERT_REQUIRED`, hostname checked, TLS 1.2+.
- **Tokens redacted** from logs via a logging filter (covers `API_TOKEN`,
  `Authorization:`, `Auth-API-Token:`, `Bearer …`).
- **Strict input validation** for zone, record, IPv4, IPv6, TTL, interval —
  single source of truth in [`src/hetzner_ddns/validation.py`](src/hetzner_ddns/validation.py).
- **No `shell=True`.** All subprocess calls use fixed-argv lists.
- **Supply chain:** signed commits (optional), Dependabot, CodeQL weekly,
  OpenSSF Scorecard, gitleaks, pip-audit + OSV in CI, Trivy + Grype for
  images, hadolint for the Dockerfile, SBOMs (SPDX + CycloneDX), SLSA L3
  provenance, Sigstore cosign signatures, PyPI OIDC trusted publishing.

Read the full threat model in [SECURITY.md](SECURITY.md) and
[docs/security.md](docs/security.md). Please report vulnerabilities
privately — see [SECURITY.md § Reporting a vulnerability](SECURITY.md).

## Development

Requires [uv](https://docs.astral.sh/uv/) and Python 3.10+.

```bash
# Bootstrap
uv sync --all-groups

# The Big Four — all must pass
uv run ruff check . && uv run ruff format --check .
uv run mypy
HETZNER_DDNS_DISABLE_OP=1 uv run pytest
uv run bandit -r src -c pyproject.toml

# Full local verification (mirrors CI)
uv run pip-audit --disable-pip

# Build artifacts
uv build
docker build -f docker/Dockerfile -t hetzner-ddns:dev .
```

Install the pre-commit hooks once:

```bash
uv run pre-commit install
```

## Testing

The test suite is split into three tiers and runs against Python 3.10, 3.11,
3.12, and 3.13:

- `tests/unit/` — fast, isolated, no network.
- `tests/integration/` — real HTTP against `pytest-httpserver` fixtures.
- `tests/e2e/` — drive `cli.main([...])` end-to-end with `HETZNER_DDNS_DISABLE_OP=1`.

```bash
HETZNER_DDNS_DISABLE_OP=1 uv run pytest            # all tiers
HETZNER_DDNS_DISABLE_OP=1 uv run pytest -m unit    # just units
HETZNER_DDNS_DISABLE_OP=1 uv run pytest -m e2e -ra # just e2e
```

Coverage must stay at or above **90 %** — enforced in `pyproject.toml` and
CI. HTML coverage lands in `htmlcov/` after a run.

## Project layout

```text
src/hetzner_ddns/     # runtime package (stdlib-only)
  ├── cli.py           argparse, signals, exit codes
  ├── config.py        env > file > 1Password loader
  ├── hetzner.py       retrying HTTPS client
  ├── ip.py            public-IP discovery with fallback
  ├── logging_setup.py text + JSON logging with redaction
  ├── state.py         atomic 0600 JSON cache
  ├── updater.py       pure plan + apply reconciliation
  └── validation.py    strict input validators

tests/                unit / integration / e2e
etc/                  config example + hardened systemd units
docker/               distroless Dockerfile + compose
docs/                 architecture, security, runbook, ADRs
.github/workflows/    CI, CodeQL, Scorecard, Dependency-Review, release
.claude/              agents, slash commands, permissions (KI-ready)
```

## Documentation

- [`CLAUDE.md`](CLAUDE.md) — project invariants & collaboration rules for AI agents.
- [`docs/architecture.md`](docs/architecture.md) — module diagram, run semantics, failure modes.
- [`docs/security.md`](docs/security.md) — threat model, trust boundaries, limitations.
- [`docs/runbook.md`](docs/runbook.md) — operations playbook.
- [`docs/adr/`](docs/adr) — architecture decision records.
- [`CHANGELOG.md`](CHANGELOG.md) — [Keep a Changelog](https://keepachangelog.com).
- [`CONTRIBUTING.md`](CONTRIBUTING.md) & [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## License

[GPL-3.0-or-later](LICENSE) © HetznerDDNSPy contributors.

This program is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version. It is distributed **without any warranty** —
see the [LICENSE](LICENSE) for full terms.

Hetzner and the Hetzner DNS API are trademarks of their respective owners.
This project is not affiliated with or endorsed by Hetzner Online GmbH.
