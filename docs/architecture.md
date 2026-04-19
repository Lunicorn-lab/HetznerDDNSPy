# Architecture

```
 ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
 │ cli.py       │──▶│ config.py    │──▶│ validation.py │
 │ (entry)      │   │ load_config  │   │ (pure funcs)  │
 └──────┬───────┘   └──────────────┘   └──────────────┘
        │                                      ▲
        │                                      │
        ▼                                      │
 ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
 │ updater.py   │──▶│ ip.py        │──▶│ (public ip   │
 │ run_once()   │   │ discover_*   │   │  providers)  │
 │ plan_actions │   └──────────────┘   └──────────────┘
 │              │──▶┌──────────────┐
 │              │   │ hetzner.py   │──▶ Hetzner DNS API (HTTPS)
 │              │   │ API client   │
 │              │   └──────────────┘
 │              │──▶┌──────────────┐
 │              │   │ state.py     │──▶ /var/lib/hetzner_ddns/state.json
 │              │   └──────────────┘
 └──────┬───────┘
        │
        ▼
 ┌──────────────┐
 │ logging_setup│──▶ journald / stdout
 │ redact + JSON│
 └──────────────┘
```

## Module responsibilities

| Module               | Responsibility | Pure? |
| -------------------- | -------------- | ----- |
| `cli.py`             | Argparse, exit codes, signal handling | no |
| `config.py`          | Load + validate config from env/file/`op` | no (I/O) |
| `validation.py`      | Zone / record / IP / TTL validators | **yes** |
| `ip.py`              | Public-IP discovery with fallback | no (HTTP) |
| `hetzner.py`         | Hetzner API client, retries, backoff | no (HTTP) |
| `state.py`           | Persistent IP cache (atomic JSON) | no (FS) |
| `updater.py`         | Reconciliation planner + applier | partly (`plan_actions` is pure) |
| `logging_setup.py`   | Structured/text logging, secret redaction | no (I/O) |
| `errors.py`          | Typed exception hierarchy | yes |

## Run semantics

### `--once` (default, used by systemd timer)

1. Load config, configure logging.
2. Load previous IP state.
3. Discover current public IPs (IPv4 + IPv6 as configured).
4. **If unchanged**, exit 0 without any Hetzner API call.
5. Otherwise: find zone → list records → diff → create/update → persist
   new state.

### `--daemon`

Runs `--once` in a loop every `INTERVAL` seconds, responding to SIGTERM/SIGINT
within 1 s. Intended for container deployments where a systemd timer is not
available.

## Failure modes

| Failure                          | Behaviour |
| -------------------------------- | --------- |
| Config invalid / missing token   | Exit 2, clear log message |
| IPv4 lookup fails, IPv6 succeeds | Proceed with IPv6 only; logged as WARNING |
| Zone not found                   | Exit 4, logged as ERROR |
| HTTP 401 / 403                   | Raise `AuthError`, exit 4 (no retry) |
| HTTP 429 / 5xx                   | Exp. backoff with jitter, up to 5 retries |
| State file corrupt               | Silently reset — will re-sync on next run |

## Design trade-offs

- **Stdlib-only runtime** keeps the attack surface minimal and the install
  drop-in friendly. Cost: no `requests`, no `httpx`, no `pydantic`.
- **One state file**, no DB. Cost: no history of changes. Mitigation: logs
  go to journald.
- **Simple retries**, no circuit breaker. The Hetzner API is reliable
  enough and the cost of a missed tick is ~5 minutes.
- **Systemd timer, not daemon**, for bare-metal deployments. Cost: small
  startup overhead. Gain: no long-lived state, easier auditing.
