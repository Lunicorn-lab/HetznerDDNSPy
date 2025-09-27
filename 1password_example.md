# 1Password CLI Example

This file shows example steps to store and retrieve the Hetzner API token with the 1Password CLI (`op`).

## Prerequisites
- Install `op` on the server or the user that will run the service. See: https://developer.1password.com/docs/cli/get-started/
- Sign in on the server (or an interactive session) with `op signin` so the session environment is set.

## Example: store a token (local machine)
Run on your workstation (not required on the server):

```bash
# create a simple item containing the token (this may vary with op versions)
# simpler approach: create a "Secure Note" or "API Credential" with a custom field "API_TOKEN"
op item create --title "Hetzner DDNS" --category "password"       --label API_TOKEN="paste-your-token-here"
```

If `op item create` complains about fields, you can create via the 1Password web UI and add a custom field named `API_TOKEN`.

## Example: retrieve token (server side)

After `op signin` (interactive), you can test retrieval like this:

```bash
# raw field (if supported)
op item get "Hetzner DDNS" --fields API_TOKEN --raw

# or fetch JSON and extract the value
op item get "Hetzner DDNS" --format json | jq -r '.fields[] | select(.label=="API_TOKEN") | .value'
```

## Using `op` in non-interactive services
For non-interactive services you must either:
- Use a session environment variable `OP_SESSION_<ACCOUNT>` made available to the service unit, or
- Export the token into `/usr/local/etc/hetzner_ddns.conf` securely during deploy, or
- Use a dedicated automation user that has the `op` session available.

Example approach to write token to config (run as deploy user):
```bash
TOKEN=$(op item get "Hetzner DDNS" --fields API_TOKEN --raw)
sudo tee /usr/local/etc/hetzner_ddns.conf > /dev/null <<EOF
API_TOKEN="${TOKEN}"
ZONE="example.com"
RECORDS="homelab media vpn @"
IPV4=true
IPV6=true
INTERVAL=60
TTL=60
EOF
sudo chmod 600 /usr/local/etc/hetzner_ddns.conf
```

This keeps the token in a file readable only by root. The installer will respect this file if present.
