#!/usr/bin/env bash
set -euo pipefail

export HOME="${HOME:-/root}"
APP_DIR="/opt/chronopi-app"
export QT_AUTO_SCREEN_SCALE_FACTOR="${QT_AUTO_SCREEN_SCALE_FACTOR:-0}"
export QT_ENABLE_HIGHDPI_SCALING="${QT_ENABLE_HIGHDPI_SCALING:-0}"
export QT_SCALE_FACTOR="${QT_SCALE_FACTOR:-1}"
export QT_FONT_DPI="${QT_FONT_DPI:-96}"

WIDTH="${SCREEN_WIDTH:-480}"
HEIGHT="${SCREEN_HEIGHT:-320}"
ROTATION="${SCREEN_ROTATION:-right}"
FRAMEBUFFER_DEVICE="${FRAMEBUFFER_DEVICE:-/dev/fb1}"
export FULLSCREEN_MODE="${FULLSCREEN_MODE:-1}"

if [ "$FULLSCREEN_MODE" = "1" ]; then
	QT_PLATFORM_SPEC="${QT_QPA_PLATFORM:-xcb}"
else
	QT_PLATFORM_SPEC="${QT_QPA_PLATFORM:-xcb}"
fi

if [ "${QT_PLATFORM_SPEC%%:*}" = "linuxfb" ] && [[ "$QT_PLATFORM_SPEC" != *"fb="* ]]; then
	QT_PLATFORM_SPEC="${QT_PLATFORM_SPEC}:fb=${FRAMEBUFFER_DEVICE}"
fi

export QT_QPA_PLATFORM="$QT_PLATFORM_SPEC"
export QTWEBENGINE_DISABLE_SANDBOX="${QTWEBENGINE_DISABLE_SANDBOX:-1}"

find_existing_x_session() {
	ps -eo args= | awk '
		/\/Xorg .* :[0-9]+ / {
			display = ""
			auth = ""
			for (i = 1; i <= NF; i++) {
				if ($i ~ /^:[0-9]+$/) {
					display = $i
				}
				if ($i == "-auth" && (i + 1) <= NF) {
					auth = $(i + 1)
				}
			}
			if (display != "") {
				print display " " auth
			}
		}
	' | tail -n 1
}

launch_app() {
	unclutter -idle 0.2 -root >/dev/null 2>&1 &
	exec "$APP_DIR/.venv/bin/python" -m app.main
}

if [ "${QT_QPA_PLATFORM%%:*}" != "xcb" ]; then
	export QT_QPA_FB_HIDECURSOR="${QT_QPA_FB_HIDECURSOR:-1}"
	exec "$APP_DIR/.venv/bin/python" -m app.main
fi

for _ in $(seq 1 20); do
	existing_session="$(find_existing_x_session)"
	if [ -n "$existing_session" ]; then
		break
	fi
	sleep 1
done

if [ -n "${existing_session:-}" ]; then
	export DISPLAY="$(printf '%s' "$existing_session" | awk '{print $1}')"
	existing_auth="${XAUTHORITY:-/root/.Xauthority}"
	if [ ! -f "$existing_auth" ]; then
		existing_auth="$(printf '%s' "$existing_session" | awk '{print $2}')"
	fi
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
