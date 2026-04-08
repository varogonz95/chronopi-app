#!/usr/bin/env bash
set -euo pipefail

export HOME="${HOME:-/root}"
APP_DIR="/opt/busy-time-device"

WIDTH="${SCREEN_WIDTH:-480}"
HEIGHT="${SCREEN_HEIGHT:-320}"
ROTATION="${SCREEN_ROTATION:-right}"
export FULLSCREEN_MODE="${FULLSCREEN_MODE:-1}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-linuxfb:rotation=90}"

launch_app() {
	unclutter -idle 0.2 -root >/dev/null 2>&1 &
	xrandr -o "$ROTATION" >/dev/null 2>&1 || true
	exec "$APP_DIR/.venv/bin/python" -m app.main
}

if [ "${QT_QPA_PLATFORM%%:*}" != "xcb" ]; then
	export QT_QPA_FB_HIDECURSOR="${QT_QPA_FB_HIDECURSOR:-1}"
	exec "$APP_DIR/.venv/bin/python" -m app.main
fi

existing_auth="$(
	ps -eo args= | awk '
		/\/Xorg .* :0 / {
			for (i = 1; i <= NF; i++) {
				if ($i == "-auth") {
					print $(i + 1)
					exit
				}
			}
		}
	'
)"

if pgrep -af '/Xorg .* :0' >/dev/null 2>&1; then
	export DISPLAY=:0
	if [ -n "$existing_auth" ] && [ -f "$existing_auth" ]; then
		export XAUTHORITY="$existing_auth"
	fi
	launch_app
fi

rm -f /tmp/.X0-lock
if [ -S /tmp/.X11-unix/X0 ] && ! pgrep -x Xorg >/dev/null 2>&1; then
	rm -f /tmp/.X11-unix/X0
fi

exec xinit /usr/bin/env bash -lc "export FULLSCREEN_MODE=${FULLSCREEN_MODE}; export SCREEN_WIDTH=${WIDTH}; export SCREEN_HEIGHT=${HEIGHT}; export QT_QPA_PLATFORM=${QT_QPA_PLATFORM}; unclutter -idle 0.2 -root >/dev/null 2>&1 & xrandr -o ${ROTATION} >/dev/null 2>&1 || true; exec ${APP_DIR}/.venv/bin/python -m app.main" -- :0 -nocursor -ac
