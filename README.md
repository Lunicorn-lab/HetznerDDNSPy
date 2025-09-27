# Hetzner DDNS - Minimal DynDNS Script (English)

This package contains a minimal DynDNS solution for Hetzner DNS.

Contents:
- `usr/local/bin/hetzner_ddns.py` — The DynDNS Python script (standard library only).
- `etc/hetzner_ddns.conf.example` — Example configuration.
- `etc/systemd/hetzner_ddns.service` — systemd service file.
- `etc/systemd/hetzner_ddns.timer` — systemd timer file (runs the script every minute).
- `install.sh` — Installation/bootstrap script (Debian/Ubuntu oriented).
- `1password_example.md` — Example showing how to use 1Password CLI to store & retrieve the Hetzner API token.
- `README.md` — This file.

All instructions use **Vim** when editing files.

## Features
- Updates A and AAAA records at Hetzner based on the machine's public IP.
- No external Python packages required.
- Supports injecting the Hetzner API token from 1Password CLI (`op`), environment variable `API_TOKEN`, or `/usr/local/etc/hetzner_ddns.conf`.
- Runs via systemd timer (recommended) or as a long-running service.

## Quick install (summary)
1. Upload and extract this package on your server, e.g. `/opt/hetzner_ddns`.
2. Inspect `install.sh` with Vim and run it as root:
   ```bash
   sudo vim install.sh
   sudo bash install.sh
   ```
3. Edit configuration at `/usr/local/etc/hetzner_ddns.conf` with Vim, or store the token in 1Password (see `1password_example.md`).
4. Start and check the timer:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now hetzner_ddns.timer
   sudo systemctl status hetzner_ddns.timer
   ```

## 1Password CLI integration (overview)
The script will attempt, in order:
1. Read `API_TOKEN` from the environment.
2. Read `API_TOKEN` from `/usr/local/etc/hetzner_ddns.conf`.
3. If not found, attempt to use the 1Password CLI (`op`) to fetch an item titled `Hetzner DDNS` and read the field `API_TOKEN`.

See `1password_example.md` for step-by-step examples of storing and retrieving the secret.

## Security notes
- Never commit your API token to source control.
- Prefer using a Hetzner token with minimal privileges.
- The installer creates files with restrictive permissions (`600`/`750`) and the script does not log secrets.

---
If you'd like, I can also produce a Docker image, a systemd-only variant, or adapt the package for another distro. Enjoy — and let me know if you want me to change the system user name or interval.
