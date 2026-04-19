# ADR 0001 — Stdlib-only runtime

- Status: Accepted
- Date: 2026-04-19

## Context

The original script used only CPython's standard library. That choice made
it easy to copy a single file onto a server and run it, but it pre-dated the
need for a real test suite, CI, and packaging.

The refactor introduces `uv`, `pytest`, `ruff`, etc. — but we need to decide
whether the **runtime** may now pull in `requests`, `httpx`, `pydantic`, or
similar.

## Decision

**Runtime stays stdlib-only.** Development dependencies are unrestricted
and tracked via `uv.lock`.

## Rationale

- Smaller attack surface. Zero runtime deps means zero dependency CVEs to
  patch in a production install. The project also doesn't benefit much from
  HTTP-library features (connection pooling, HTTP/2, etc.) because we make
  a handful of requests every 5 minutes.
- Simpler install. The `install.sh` needs only Python; the container image
  doesn't copy third-party wheels. Both reduce the chance of installation
  failures on odd distros.
- Faster imports, smaller memory footprint. Matches the systemd
  `MemoryMax=128M` budget comfortably.
- No meaningful loss. `urllib.request` does everything we need; `ssl` gives
  us TLS verification; `ipaddress` gives us parsing & validation;
  `subprocess` is only used (with fixed argv) for the `op` CLI fallback.

## Consequences

- Tests may depend on anything — they use `pytest-httpserver` for mocking.
- If we ever need websockets, HTTP/2, or async fan-out, revisit this ADR.
- The CI pipeline verifies that runtime code imports nothing from outside
  the stdlib (`ruff`'s `I` rules + explicit grep in `pre-commit`).
