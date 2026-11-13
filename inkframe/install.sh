#!/usr/bin/env bash
# InkFrame installer for Raspberry Pi OS Lite (Bookworm or newer).
# Run from this folder:  sudo ./install.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run with sudo:  sudo ./install.sh" >&2
  exit 1
fi

SRC="$(cd "$(dirname "$0")" && pwd)"
APP=/opt/inkframe
CONFIG=/boot/firmware/config.txt
[[ -f $CONFIG ]] || CONFIG=/boot/config.txt

echo "==> Installing system packages"
apt-get update
apt-get install -y python3-venv python3-dev git libopenjp2-7 libjpeg-dev

echo "==> Enabling SPI and I2C (needed by the screen and the PiSugar)"
raspi-config nonint do_spi 0
raspi-config nonint do_i2c 0
# The 13.3" Inky drives its own chip-select pins, so stop the SPI driver claiming them.
grep -q '^dtoverlay=spi0-0cs' "$CONFIG" || echo 'dtoverlay=spi0-0cs' >> "$CONFIG"

echo "==> Copying InkFrame to $APP"
mkdir -p "$APP"
cp -r "$SRC/inkframe" "$SRC/requirements.txt" "$APP/"

echo "==> Creating Python environment (this takes a while on a Pi Zero)"
python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install --upgrade pip
"$APP/venv/bin/pip" install -r "$APP/requirements.txt"

echo "==> Installing the InkFrame service"
mkdir -p /var/lib/inkframe
cp "$SRC/systemd/inkframe.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable inkframe.service

if ! systemctl list-unit-files | grep -q pisugar-server; then
  cat <<'EOF'

!!  PiSugar software not found.
    Install it with PiSugar's official installer (see README, step 5), choosing
    "PiSugar 3" when asked, then reboot:
      curl https://cdn.pisugar.com/release/pisugar-power-manager.sh | sudo bash

EOF
fi

echo
echo "Done. Reboot to start:  sudo reboot"
echo "Then open http://$(hostname).local on your phone."
