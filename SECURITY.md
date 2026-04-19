# Security Policy

We take security seriously. This page documents how to report issues, which
versions we support, and the defences already in place.

## Supported versions

| Version | Supported                  |
| ------- | -------------------------- |
| 2.x     | :white_check_mark: active  |
| 1.x     | :x: end-of-life (2026-04)  |

## Reporting a vulnerability

**Please do not open a public issue.** Report privately via GitHub's private
vulnerability disclosure:

> https://github.com/Lunicorn/HetznerDDNSPy/security/advisories/new

Or email the maintainers (PGP key pinned in the repo) with:

- Affected version / commit SHA
- Reproduction steps or proof-of-concept
- Impact assessment (confidentiality / integrity / availability)
- Your preferred handle for credit (optional)

**Target response times**

| Severity | First response | Fix target |
| -------- | -------------- | ---------- |
| Critical | 24h            | 7 days     |
| High     | 48h            | 14 days    |
| Medium   | 5 days         | 30 days    |
| Low      | 10 days        | next minor |

We follow a **coordinated disclosure** model: once a fix is available we
publish a GHSA, CVE, and release notes. Credit goes to the reporter unless
they prefer otherwise.

---

## Defence in depth — what's already in place

### Supply chain
- **uv lockfile** committed and verified in CI.
- **pip-audit** + **OSV Scanner** on every PR.
- **Dependabot** weekly updates for `pip`, `github-actions`, `docker`.
- **GitHub Dependency Review** blocks PRs introducing high-severity CVEs or
  disallowed licences (AGPL, GPL).
- **OpenSSF Scorecard** runs weekly.
- **SLSA Level 3 provenance** attached to every tagged release.
- **Sigstore cosign** signs container images keyless via OIDC.
- **SBOM** (SPDX + CycloneDX) generated for every release and the container.
- **Trusted publishing** to PyPI via GitHub OIDC (no long-lived tokens).

### Source code
- **CodeQL** (`security-and-quality` suite) on push/PR.
- **Bandit** (medium+) and **Semgrep** (OWASP Top 10, Python, secrets,
  supply-chain, Dockerfile rule-packs) on every PR with SARIF upload.
- **Gitleaks** secret scanning on the full history.
- **Strict input validation** for zone, record name, IPv4, IPv6, TTL,
  interval — see [`src/hetzner_ddns/validation.py`](src/hetzner_ddns/validation.py).
- **Log redaction** of any `API_TOKEN`/`Auth-API-Token`/`Bearer` occurrence.
- No `eval`, no `exec`, no shell invocation with untrusted data.

### Runtime (systemd)
- Dedicated system user `hetzner-ddns`, no shell, no home.
- Service runs as **`Type=oneshot`** triggered by a timer — the previous
  long-lived daemon-loop-inside-a-timer bug is gone.
- Hardening: `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`,
  `PrivateTmp`, `PrivateDevices`, `RestrictAddressFamilies=AF_INET AF_INET6
  AF_UNIX`, `SystemCallFilter=@system-service` minus `@privileged @resources
  @mount @debug @reboot @swap @raw-io`, empty `CapabilityBoundingSet`,
  `MemoryDenyWriteExecute`, `LockPersonality`, `RestrictNamespaces`,
  `RestrictRealtime`, `RestrictSUIDSGID`, `UMask=0077`.
- Resource limits: `MemoryMax=128M`, `TasksMax=32`, `CPUQuota=25%`,
  `LimitNOFILE=256`.
- Config file mode `0600` / `0640` root-owned, readable by the service
  group only.
- State file mode `0600` in `/var/lib/hetzner_ddns` (`StateDirectoryMode=0750`).

### Runtime (container)
- Base: `gcr.io/distroless/python3-debian12:nonroot` (pinned by digest).
- **No shell, no package manager**, UID/GID `65532`.
- Read-only root FS (`read_only: true` in the compose file).
- All Linux capabilities dropped.
- `no-new-privileges: true`.
- Python venv built in a separate stage and copied over.
- Multi-arch (amd64 + arm64), SBOM + SLSA provenance attached by buildx.

### Network
- TLS 1.2+ with full certificate verification (`ssl.CERT_REQUIRED` +
  `check_hostname=True`). Plain HTTP is rejected except for loopback
  addresses used by the test suite.
- Per-request 15s timeout, exponential backoff with jitter on retries,
  explicit handling of HTTP 401/403/429/5xx.
- Multiple IPv4 / IPv6 providers with ordered fallback; any response that
  fails IP validation is discarded.

### Secrets
- `API_TOKEN` never logged. Redaction filter in `logging_setup.py` covers
  `Auth-API-Token`, `api_token=`, and `Bearer <token>` forms.
- Three supported sources (env > config file > 1Password CLI). The CLI
  path is the only place we invoke `subprocess` — always with a fixed
  `argv` list, never `shell=True`.
- The 1Password lookup can be disabled via `HETZNER_DDNS_DISABLE_OP=1`.

---

## Threat model (summary)

| Threat                                          | Mitigation |
| ----------------------------------------------- | ---------- |
| Leaked API token in logs                        | Redacting logger filter |
| Malicious IP-provider returning bad data        | Strict IP parsing + validation + provider fallback |
| Hetzner API MITM / downgrade                    | TLS 1.2+, full cert verification, HSTS-like scheme enforcement |
| Config file tampering                           | Mode `0600`, root-owned; state file mode `0600` |
| Service privilege escalation                    | systemd hardening, dropped capabilities, seccomp filter |
| Supply-chain injection (dep)                    | uv.lock pinning, pip-audit, OSV, dependency-review, SLSA |
| Supply-chain injection (image)                  | Distroless base pinned by digest, Trivy + Grype + cosign |
| Secret commit                                   | Gitleaks in CI + pre-commit |
| Weak auth error handling                        | 401/403 mapped to `AuthError`, no retries, explicit exit code |
| Runtime OOM / DoS                               | `MemoryMax`, `TasksMax`, `CPUQuota`, `LimitNOFILE` |

See [`docs/security.md`](docs/security.md) for the extended threat model.
