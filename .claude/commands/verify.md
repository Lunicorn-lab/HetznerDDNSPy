---
description: Run the full local verification suite (lint, type, test, security).
---

Run these commands in sequence, stopping at the first failure:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
HETZNER_DDNS_DISABLE_OP=1 uv run pytest
uv run bandit -r src -c pyproject.toml
uv run pip-audit --disable-pip
```

Report each command's pass/fail status, plus the final coverage percent from
pytest. If something fails, fix the smallest reasonable thing and re-run —
do not suppress failures by loosening configuration.
