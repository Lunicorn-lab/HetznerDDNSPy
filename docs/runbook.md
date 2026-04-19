# Operations Runbook

Operational playbook for people running `hetzner-ddns` in production.

## Health checks

```bash
# Is the timer active?
systemctl status hetzner_ddns.timer

# When did we last run and when will we run next?
systemctl list-timers | grep hetzner_ddns

# Last run logs (last 100 lines)
journalctl -u hetzner_ddns.service -n 100 --no-pager

# Live tail
journalctl -u hetzner_ddns.service -f
```

Expected line in a healthy boring run (IP unchanged):

```
public IPs unchanged — skipping Hetzner sync (v4=… v6=…)
```

## Common incidents

### 1. `API_TOKEN missing`

**Symptom**: service exits immediately, `configuration error` in log.

**Fix**:
```bash
sudo -u hetzner-ddns /usr/local/bin/hetzner-ddns --check-config
# edit /usr/local/etc/hetzner_ddns.conf and re-run
```

### 2. `auth rejected by Hetzner API (401|403)`

**Symptom**: every run exits 4. Hetzner is answering but refuses the token.

**Fix**: rotate the token at <https://dns.hetzner.com/settings/api-token>,
update either the config file (mode 0600!) or the 1Password entry, then:
```bash
sudo systemctl start hetzner_ddns.service
```

### 3. `All providers failed` for IPv4/IPv6

**Symptom**: transient warning lines. If it persists: the host has lost
Internet, or all three providers are blocking this egress IP.

**Diagnostics**:
```bash
curl -4 -sv https://ipv4.icanhazip.com
curl -6 -sv https://ipv6.icanhazip.com
```

If only IPv6 fails, the host may not have IPv6 connectivity — set `IPV6=false`.

### 4. Record stuck at stale IP

**Symptom**: Hetzner web UI shows an old address even though logs say the
update succeeded.

**Diagnostics**:
```bash
# Force a fresh discovery + push, ignoring state cache:
sudo systemctl stop hetzner_ddns.timer
sudo rm -f /var/lib/hetzner_ddns/state.json
sudo systemctl start hetzner_ddns.service
sudo systemctl enable --now hetzner_ddns.timer
```

Check TTL propagation with `dig +trace` from an external resolver.

### 5. Container image fails to start

```bash
docker logs hetzner-ddns
docker run --rm ghcr.io/lunicorn/hetznerddnspy:latest --check-config
```

If the container is crash-looping with `configuration error`, verify the
env-file is mounted and contains `API_TOKEN` and `ZONE`.

## Rolling updates

### Host (systemd)

```bash
# Backup the old venv
sudo mv /opt/hetzner-ddns /opt/hetzner-ddns.bak

# Re-run the installer
cd /path/to/HetznerDDNSPy
sudo ./install.sh

# Verify
sudo -u hetzner-ddns /usr/local/bin/hetzner-ddns --check-config
sudo systemctl start hetzner_ddns.service
```

### Container

```bash
docker compose pull && docker compose up -d
```

## Rollback

Both deployment modes support a simple rollback: restore the previous
`/opt/hetzner-ddns.bak` venv or pin the previous container tag.

## Monitoring suggestions

- journald → Loki / Vector: filter `SYSLOG_IDENTIFIER=hetzner-ddns`, alert
  on ERROR.
- Prometheus: watch `systemd_unit_state{name="hetzner_ddns.timer"}`; alert
  if not `active`.
- Blackbox probe against your DDNS name: alert if resolution diverges from
  this host's public IP for more than `2 × INTERVAL`.
