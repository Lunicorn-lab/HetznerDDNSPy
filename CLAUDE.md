# CLAUDE.md — project context for AI collaborators

This file is the single source of truth for any AI agent working in this
repo. It summarises the invariants, conventions, and trusted commands so
that agents can act quickly without re-deriving the project from scratch.

## Mission

A minimal, secure DynDNS updater for the Hetzner DNS API. Runs either as a
systemd timer (bare metal) or a distroless container (Docker/Kubernetes).

## Invariants — do not violate without explicit approval

1. **Runtime is stdlib-only.** Anything imported by `src/hetzner_ddns/` at
   runtime must come from CPython's standard library. Dev tooling is free.
2. **TLS is always verified.** No `ssl.CERT_NONE`, no `check_hostname=False`
   for anything talking to a real host. Tests use loopback and may relax.
3. **Tokens never enter logs unredacted.** The redaction filter in
   `logging_setup.py` must cover any new secret format.
4. **No `shell=True`, no string-built commands.** Subprocess calls use a
   fixed `argv` list.
5. **Input validation at every boundary.** Zone, record, IP, TTL — always
   via `validation.py`, never ad-hoc regexes inline.
6. **Systemd hardening is a one-way ratchet.** Don't relax settings in
   `etc/systemd/hetzner_ddns.service`; add them if anything.
7. **Tests first.** Any behavioural change ships with a test. 90 % coverage
   is the floor.
8. **Conventional commits.** `feat(ip): add provider for …`, `fix(hetzner):
   handle 503 retries`, etc.

## Repo map

```
src/hetzner_ddns/
├── __init__.py        version + package
├── __main__.py        python -m hetzner_ddns entry
├── cli.py             argparse, signals, exit codes
├── config.py          load + validate (env > file > op)
├── errors.py          typed exceptions
├── hetzner.py         API client with retry/backoff
├── ip.py              public IP discovery + fallback
├── logging_setup.py   text + JSON, redaction filter
├── state.py           atomic JSON cache at 0600
├── updater.py         plan + apply reconciliation
└── validation.py      strict input validators

tests/                  unit, integration, e2e (pytest-httpserver)
etc/                    hetzner_ddns.conf.example, systemd units
docker/                 Dockerfile (distroless), compose
docs/                   architecture, security, runbook, ADRs
.github/                CI, release, scorecard, codeql, dependabot
```

## Trusted commands

```bash
# Bootstrap
uv sync --all-groups

# The Big Four — all must pass
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest                          # ≥ 90 % coverage required
uv run bandit -r src -c pyproject.toml

# Security audit (run together with CI)
uv run pip-audit --disable-pip
uv run pytest -m e2e -ra

# Build
uv build
docker build -f docker/Dockerfile -t hetzner-ddns:dev .

# Local smoke-test the CLI
HETZNER_DDNS_DISABLE_OP=1 uv run hetzner-ddns --check-config --log-level DEBUG
```

Set `HETZNER_DDNS_DISABLE_OP=1` in any non-production context so the 1Password
lookup never hangs the process.

## When you add a new module

1. It lives under `src/hetzner_ddns/`.
2. It exports only what it must (prefer a small public API).
3. It is fully type-hinted (mypy strict).
4. It has a matching `tests/unit/test_<module>.py`.
5. If it touches the network or disk, also add an integration test.
6. Update `docs/architecture.md` if you added a new component.

## When you change behaviour

1. Test first — write a failing test that captures the new behaviour.
2. Make it pass with the minimum diff.
3. Update `CHANGELOG.md` under `## [Unreleased]`.
4. If trust boundaries change, update `SECURITY.md` and `docs/security.md`.

## Non-goals

- Web UI, admin dashboard, database.
- Multi-provider DNS (Cloudflare, Route53, etc.). Keep focus on Hetzner.
- Service discovery, mDNS, anything not A/AAAA reconciliation.

## Release

Maintainers tag `vX.Y.Z`; the release workflow handles PyPI (OIDC), GHCR
(cosign-signed, SLSA L3), SBOMs. Never publish manually.

## Agents & slash commands

- `.claude/agents/reviewer.md` — security-leaning code reviewer
- `.claude/agents/test-writer.md` — focused test-coverage expansion
- `.claude/commands/verify.md` — runs the full local check
- `.claude/commands/release-notes.md` — drafts a CHANGELOG entry from
  `git log`

Read those files before using them so you know what they expect.
