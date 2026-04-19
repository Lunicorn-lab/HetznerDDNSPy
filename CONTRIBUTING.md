# Contributing

Thank you for considering a contribution! This project aims to stay small,
legible, and secure — please keep that spirit in mind.

## Ground rules

- **Runtime has zero non-stdlib dependencies.** Dev tools are fine; anything
  imported by `src/hetzner_ddns/` at runtime must come from CPython's stdlib.
- **Security is not optional.** See [`SECURITY.md`](SECURITY.md) — do not
  relax any hardening setting (systemd, TLS, validation) without a linked
  rationale.
- **Every PR must be green.** Lint, typecheck, tests, SAST, SCA, secret scan,
  CodeQL.

## Quickstart

```bash
# 1. Fork + clone
git clone https://github.com/YOUR-USER/HetznerDDNSPy.git
cd HetznerDDNSPy

# 2. Bootstrap tooling (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --all-groups
uv run pre-commit install

# 3. Run the full local check
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest
uv run bandit -r src -c pyproject.toml
```

## Commit style

Follow **Conventional Commits**:

```
<type>(<scope>): <short summary>

<body — optional, wrap at 72>

<footer — optional, e.g. "Closes #123">
```

Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `build`,
`ci`, `security`.

Sign your commits (`git commit -S`) — this repo expects signed commits on
`main` once branch protection is fully enabled.

## Pull request checklist

Before requesting review:

- [ ] Tests cover the change (unit, integration, or e2e as appropriate)
- [ ] `uv run pytest` passes with ≥ 90 % coverage
- [ ] `uv run mypy` is clean
- [ ] `uv run ruff check .` is clean
- [ ] `SECURITY.md` updated if the change touches trust boundaries
- [ ] `CHANGELOG.md` entry added under *Unreleased*

## Releasing (maintainers)

1. Update `pyproject.toml` version and `CHANGELOG.md`.
2. Merge into `main` via PR.
3. Tag `vX.Y.Z` — the release workflow handles PyPI, GHCR, SBOM, signing.

## Code of conduct

See [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Short version: be kind,
assume good faith, disagree with ideas not people.
