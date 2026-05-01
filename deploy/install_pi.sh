#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/chronopi-app"
REPO_SOURCE="${1:-$PWD}"

apt-get update

apt_cache_install() {
  local pkg
  local available=()
  for pkg in "$@"; do
    if apt-cache show "$pkg" >/dev/null 2>&1; then
      available+=("$pkg")
    fi
  done

  if [ "${#available[@]}" -gt 0 ]; then
    apt-get install -y "${available[@]}"
  fi
}

apt_cache_install \
  python3-venv python3-pip xserver-xorg xinit unclutter rsync \
  libdbus-1-3 libegl1 libfontconfig1 libx11-xcb1 libxkbcommon-x11-0 \
  libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
  libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-util1 \
  libxcb-xfixes0 libxcb-xinerama0

apt_cache_install \
  libevent-2.1-7t64 libevent-2.1-6 libevent-pthreads-2.1-7 \
  libevent-pthreads-2.1-6 libwebpmux3 libwebpmux4 libwebpdemux3 \
  libwebpdemux4 libwebp6 libwebp7 libwebp5 libwebp-dev \
  libqt6webengine6 libqt6webenginewidgets6 python3-pyside6.qtwebenginewidgets \
  python3-pyside6.qtwebenginequick python3-pyside6.qtwebenginecore

mkdir -p "$APP_DIR"
mkdir -p "$APP_DIR/data"
rsync -av --delete \
	--exclude '.env' \
	--exclude 'data/tokens.json' \
	"$REPO_SOURCE/" "$APP_DIR/"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements-pi.txt"
chmod +x "$APP_DIR/deploy/kiosk.sh"
install -m 644 "$APP_DIR/deploy/chronopi.service" /etc/systemd/system/chronopi.service
systemctl daemon-reload
systemctl enable chronopi.service
systemctl restart chronopi.service
