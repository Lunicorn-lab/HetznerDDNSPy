#!/usr/bin/env bash
set -euo pipefail
#
# Installer / bootstrap for Hetzner DDNS (Debian/Ubuntu)
#
PACKAGE_DIR="/opt/hetzner_ddns"
INSTALL_BIN="/usr/local/bin/hetzner_ddns.py"
CONFIG_PATH="/usr/local/etc/hetzner_ddns.conf"
SYSTEMD_SERVICE="/etc/systemd/system/hetzner_ddns.service"
SYSTEMD_TIMER="/etc/systemd/system/hetzner_ddns.timer"
USERNAME="regen"

echo "Starting install (requires root)"

apt update
apt install -y python3 vim sudo passwd util-linux curl ca-certificates jq

echo "If you want to use 1Password CLI, install 'op' and sign in the user that will run the service."
echo "See: https://developer.1password.com/docs/cli/get-started/"

if id -u "$USERNAME" >/dev/null 2>&1; then
  echo "User $USERNAME already exists"
else
  echo "Creating user $USERNAME ..."
  adduser --disabled-password --gecos "" "$USERNAME"
  echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME
  chmod 440 /etc/sudoers.d/$USERNAME
fi

mkdir -p "$PACKAGE_DIR"
cp -r . "$PACKAGE_DIR/"
chmod -R 750 "$PACKAGE_DIR"

install -m 750 "$PACKAGE_DIR/usr/local/bin/hetzner_ddns.py" "$INSTALL_BIN"

mkdir -p "$(dirname "$CONFIG_PATH")"
if [ ! -f "$CONFIG_PATH" ]; then
  cp "$PACKAGE_DIR/etc/hetzner_ddns.conf.example" "$CONFIG_PATH"
  chmod 600 "$CONFIG_PATH"
  chown root:root "$CONFIG_PATH"
  echo "Please edit $CONFIG_PATH with vim or inject API token via 1Password (see 1password_example.md)"
else
  echo "$CONFIG_PATH exists — skipping."
fi

install -m 644 "$PACKAGE_DIR/etc/systemd/hetzner_ddns.service" "$SYSTEMD_SERVICE"
install -m 644 "$PACKAGE_DIR/etc/systemd/hetzner_ddns.timer" "$SYSTEMD_TIMER"

systemctl daemon-reload
systemctl enable --now hetzner_ddns.timer

echo "Install finished. Edit config with Vim:"
echo "  sudo -u root vim $CONFIG_PATH"
echo ""
echo "Example: to inject token from 1Password into config (run as a user who ran 'op signin'): "
echo "  TOKEN=$(op item get "Hetzner DDNS" --fields API_TOKEN --raw)"
echo "  sudo tee $CONFIG_PATH >/dev/null <<EOF"
echo 'API_TOKEN="${TOKEN}"'
echo 'ZONE="example.com"'
echo 'RECORDS="homelab media vpn @"'
echo 'IPV4=true'
echo 'IPV6=true'
echo 'INTERVAL=60'
echo 'TTL=60'
echo 'EOF'
