#!/usr/bin/env bash
# Installer for Hetzner DDNS on systemd Linux (Debian/Ubuntu/Fedora/Arch).
#
# What it does (all idempotent):
#   1. Installs uv and creates an isolated Python environment in /opt/hetzner-ddns
#   2. Installs the package from the current checkout (or PyPI if HDDNS_FROM_PYPI=1)
#   3. Creates a dedicated system user 'hetzner-ddns' with no shell, no home
#   4. Installs the systemd service + timer (hardened)
#   5. Installs a default config at /usr/local/etc/hetzner_ddns.conf (mode 0600)
#
# Usage:
#   sudo ./install.sh
#
# Environment variables:
#   HDDNS_USER        — system user to create (default: hetzner-ddns)
#   HDDNS_PREFIX      — install prefix (default: /opt/hetzner-ddns)
#   HDDNS_FROM_PYPI   — if set to 1, install from PyPI instead of local sources
#   HDDNS_VERSION     — version constraint for PyPI install (default: latest)
#
set -Eeuo pipefail
shopt -s inherit_errexit 2>/dev/null || true

HDDNS_USER="${HDDNS_USER:-hetzner-ddns}"
HDDNS_GROUP="${HDDNS_GROUP:-$HDDNS_USER}"
HDDNS_PREFIX="${HDDNS_PREFIX:-/opt/hetzner-ddns}"
HDDNS_BIN="/usr/local/bin/hetzner-ddns"
HDDNS_CONFIG="/usr/local/etc/hetzner_ddns.conf"
HDDNS_STATE_DIR="/var/lib/hetzner_ddns"
SYSTEMD_DIR="/etc/systemd/system"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

log() { printf '\e[1;34m[install]\e[0m %s\n' "$*"; }
die() { printf '\e[1;31m[error]\e[0m %s\n' "$*" >&2; exit 1; }

require_root() {
  [[ $EUID -eq 0 ]] || die "this script must be run as root (try: sudo $0)"
}

detect_os() {
  [[ -r /etc/os-release ]] || die "cannot detect OS (missing /etc/os-release)"
  # shellcheck disable=SC1091
  . /etc/os-release
  log "detected: ${PRETTY_NAME:-$ID}"
}

install_uv() {
  if command -v uv >/dev/null 2>&1; then
    log "uv already installed: $(uv --version)"
    return
  fi
  log "installing uv (official script, https)"
  # Pinned by hash in CI; here we trust the upstream-signed installer.
  curl -LsSf --proto '=https' --tlsv1.2 https://astral.sh/uv/install.sh -o /tmp/uv-install.sh
  sh /tmp/uv-install.sh
  rm -f /tmp/uv-install.sh
  export PATH="$HOME/.local/bin:$PATH"
}

ensure_user() {
  if id -u "$HDDNS_USER" >/dev/null 2>&1; then
    log "user $HDDNS_USER exists"
    return
  fi
  log "creating system user $HDDNS_USER (no shell, no home)"
  useradd --system --no-create-home --shell /usr/sbin/nologin "$HDDNS_USER"
}

install_app() {
  log "preparing $HDDNS_PREFIX"
  install -d -m 0755 -o root -g root "$HDDNS_PREFIX"

  if [[ "${HDDNS_FROM_PYPI:-0}" = "1" ]]; then
    local spec="hetzner-ddns"
    [[ -n "${HDDNS_VERSION:-}" ]] && spec="hetzner-ddns==${HDDNS_VERSION}"
    log "installing $spec from PyPI into $HDDNS_PREFIX"
    uv venv --python 3.12 "$HDDNS_PREFIX/venv"
    uv pip install --python "$HDDNS_PREFIX/venv/bin/python" "$spec"
  else
    log "installing from local checkout at $SCRIPT_DIR"
    uv venv --python 3.12 "$HDDNS_PREFIX/venv"
    uv pip install --python "$HDDNS_PREFIX/venv/bin/python" "$SCRIPT_DIR"
  fi

  log "linking entry point at $HDDNS_BIN"
  ln -sf "$HDDNS_PREFIX/venv/bin/hetzner-ddns" "$HDDNS_BIN"
}

install_config() {
  install -d -m 0755 -o root -g root "$(dirname "$HDDNS_CONFIG")"
  if [[ -f "$HDDNS_CONFIG" ]]; then
    log "config exists at $HDDNS_CONFIG — leaving untouched"
    chmod 0600 "$HDDNS_CONFIG"
    chown root:"$HDDNS_GROUP" "$HDDNS_CONFIG"
    return
  fi
  log "installing default config at $HDDNS_CONFIG"
  install -m 0640 -o root -g "$HDDNS_GROUP" \
    "$SCRIPT_DIR/etc/hetzner_ddns.conf.example" "$HDDNS_CONFIG"
}

install_state_dir() {
  install -d -m 0750 -o "$HDDNS_USER" -g "$HDDNS_GROUP" "$HDDNS_STATE_DIR"
}

install_systemd_units() {
  log "installing systemd units"
  install -m 0644 -o root -g root \
    "$SCRIPT_DIR/etc/systemd/hetzner_ddns.service" "$SYSTEMD_DIR/hetzner_ddns.service"
  install -m 0644 -o root -g root \
    "$SCRIPT_DIR/etc/systemd/hetzner_ddns.timer" "$SYSTEMD_DIR/hetzner_ddns.timer"
  systemctl daemon-reload
}

verify_and_enable() {
  log "validating config via hetzner-ddns --check-config"
  if sudo -u "$HDDNS_USER" "$HDDNS_BIN" --check-config; then
    log "enabling timer"
    systemctl enable --now hetzner_ddns.timer
    systemctl status --no-pager hetzner_ddns.timer || true
  else
    log "configuration is incomplete — edit $HDDNS_CONFIG then run:"
    log "  sudo systemctl enable --now hetzner_ddns.timer"
  fi
}

main() {
  require_root
  detect_os
  install_uv
  ensure_user
  install_app
  install_config
  install_state_dir
  install_systemd_units
  verify_and_enable
  log "done."
}

main "$@"
