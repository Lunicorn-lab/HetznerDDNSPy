# Summary

<!-- 1–3 bullets: what changed and why. -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation / chore

## Security checklist

- [ ] No secrets or tokens in the diff
- [ ] Input validation considered for any new user-/network-facing data
- [ ] No new shell-outs using untrusted input (`subprocess`, `os.system`)
- [ ] Any new network endpoint uses TLS with full cert verification
- [ ] Systemd hardening not relaxed (if applicable)
- [ ] Dockerfile stays non-root & distroless (if applicable)

## Test plan

- [ ] `uv run ruff check . && uv run ruff format --check .`
- [ ] `uv run mypy`
- [ ] `uv run pytest`
- [ ] `uv run bandit -r src -c pyproject.toml`

## Notes for reviewers

<!-- anything that needs extra attention: rollout plan, migration, etc. -->
