# Security architecture

This document complements [`SECURITY.md`](../SECURITY.md) with the detailed
threat model and design rationale. If you are auditing or hardening this
tool, start here.

## Scope

- **In-scope**: the updater service, its config & state files, its container
  image, the CI/CD pipeline, and the systemd unit files.
- **Out-of-scope**: the Hetzner DNS service itself; the host OS; the user's
  1Password account; DNS-resolver hijacking by upstream ISPs.

## Trust boundaries

```
 ┌───────────────────────────┐
 │  Admin / Deploy           │   ← trusted: manages token, config, host
 └──────────────┬────────────┘
                │ writes
 ┌──────────────▼────────────┐
 │  Config file /            │   ← 0600, root-owned, read by service group
 │  ENV / 1Password CLI      │
 └──────────────┬────────────┘
                │ reads
 ┌──────────────▼────────────┐
 │  hetzner-ddns process      │   ← non-root, hardened systemd, ~128 MB RAM
 └──────────────┬────────────┘
                │ HTTPS (TLS 1.2+, cert verified)
 ┌──────────────▼────────────┐
 │  icanhazip / ifconfig.me / │   ← semi-trusted (validated response)
 │  ipify (IP providers)     │
 └──────────────┬────────────┘
                │
 ┌──────────────▼────────────┐
 │  Hetzner DNS API           │   ← trusted endpoint; token-authenticated
 └───────────────────────────┘
```

## Attacker model

| Attacker                      | Capabilities | Mitigations |
| ----------------------------- | ------------ | ----------- |
| Unprivileged local user       | read `/etc` world-readable parts, ptrace other unprivileged processes | config mode 0600, dedicated `hetzner-ddns` user, `NoNewPrivileges`, `RestrictNamespaces` |
| Network MITM on IP provider   | return arbitrary bytes as public-IP response | TLS enforced, provider fallback, strict `ipaddress` validation, non-routable ranges rejected |
| Network MITM on Hetzner API   | tamper with zones/records | TLS 1.2+, cert verification, hostname check, no insecure fallback |
| Malicious dependency          | execute arbitrary code at runtime or at install | **zero runtime deps**; uv.lock for dev; pip-audit + OSV + CodeQL + SLSA |
| Malicious base image          | compromise container runtime | distroless base pinned by digest, Trivy + Grype, signed by cosign |
| Compromised CI runner         | inject malicious artifacts | StepSecurity harden-runner in every job, minimum GitHub permissions, trusted publishing (OIDC) |
| Compromised maintainer account | push bad code to main | branch protection, CODEOWNERS review, signed commits, 2FA (repo-owner responsibility) |

## Data classification

| Data                           | Classification | Storage |
| ------------------------------ | -------------- | ------- |
| Hetzner API token              | SECRET         | 0600 config file OR env OR 1Password |
| Public IP (own)                | INTERNAL       | `/var/lib/hetzner_ddns/state.json`, 0600 |
| DNS zone / record names        | INTERNAL       | same |
| Logs                           | INTERNAL       | journald; secrets redacted before write |

## Cryptography

- TLS: system default (`ssl.create_default_context()`), minimum
  TLS 1.2 enforced by OpenSSL defaults on the target distributions.
- No cryptographic primitives are used locally — the token is a bearer
  secret, treated purely as opaque bytes.

## Known limitations

1. The tool does not currently verify the Hetzner API's certificate against
   a pinned public key. Upstream cert rotation would break pinning, so we
   rely on the system CA store.
2. The 1Password CLI lookup trusts whatever session is available to the
   calling user. Admins should ensure `op` sessions are not shared.
3. Log-level `DEBUG` may include URLs (without tokens). Avoid `DEBUG` on
   production systems with a shared journald.

## Continuous verification

Every PR and every push runs the full pipeline in
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml). CodeQL and
Scorecard run weekly on a schedule. Dependabot opens grouped PRs once a
week. SBOM + SLSA provenance are attached to every tagged release.

## Reporting

Private disclosure via GitHub Security Advisories, see
[`SECURITY.md`](../SECURITY.md).
