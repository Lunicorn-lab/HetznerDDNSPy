# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.0] — 2026-04-19

### Added
- **Full refactor** into an installable Python package
  (`src/hetzner_ddns/…`) with strict typing and 90 %+ test coverage.
- **CLI** (`hetzner-ddns`) with `--once`, `--daemon`, `--check-config`,
  `--dry-run`, `--log-level`, `--log-format`.
- **IP-state cache** at `/var/lib/hetzner_ddns/state.json` — the tool now
  only hits the Hetzner API when the public IP actually changes.
- **Provider fallback** for IPv4/IPv6 discovery across icanhazip, ifconfig.me,
  and ipify, with strict IP validation.
- **Retry & backoff** with jitter for 429/5xx/transient network errors.
- **Structured JSON logging** via `LOG_FORMAT=json`; redaction filter strips
  tokens from every log line.
- **Docker image** (distroless, non-root, multi-arch) pushed to GHCR, signed
  with Sigstore cosign and shipped with SBOM + SLSA provenance.
- **CI/CD**: ruff, mypy-strict, pytest matrix (Py 3.10–3.13), bandit,
  semgrep (OWASP), pip-audit, OSV Scanner, gitleaks, CodeQL, Trivy, Grype,
  hadolint, shellcheck, OpenSSF Scorecard, dependency-review.
- **Release pipeline**: PyPI trusted publishing (OIDC), GHCR image signing,
  SBOM (SPDX + CycloneDX), SLSA Level 3 provenance.
- **Hardened systemd unit**: `NoNewPrivileges`, `ProtectSystem=strict`,
  `SystemCallFilter`, `CapabilityBoundingSet=`, resource limits, etc.
- **Validated config** with explicit precedence (env > file > 1Password).

### Changed
- **BREAKING**: script relocated from `usr/local/bin/hetzner_ddns.py` to an
  installable package; the installer now creates a venv under
  `/opt/hetzner-ddns`.
- **BREAKING**: dedicated user renamed `regen` → `hetzner-ddns`; timer
  interval default increased from 1 min to 5 min with a random jitter of 30 s.
- **BREAKING**: the systemd service is now `Type=oneshot`; the previous
  `while True` loop inside a `Type=simple` service (which blocked timer
  re-triggering) is gone.

### Removed
- The monolithic script; see `src/hetzner_ddns/` for the new layout.
- Hardcoded username `regen` in `install.sh`.

### Security
- See [`SECURITY.md`](SECURITY.md) for the full threat model.

## [1.0.0] — 2025-09-01

- Initial release: single-file script, systemd timer, 1Password CLI support.
