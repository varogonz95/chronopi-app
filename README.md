# Chronopi

Chronopi is a portrait-oriented kiosk app for a Raspberry Pi with a TFT display. It merges upcoming availability from Google Calendar, Outlook/Microsoft 365, and Zoom into a single fullscreen dashboard designed around the supplied mockup.

## Why this stack

- Python keeps the data-provider and deployment story simple on a Raspberry Pi 3 A+.
- Qt renders the dashboard natively, which is materially lighter than keeping Chromium open all day.
- OAuth still runs on-device through a small setup server, so the Pi can refresh tokens and keep running independently.

## Features

- Fullscreen portrait dashboard with a native Qt UI, large clock, current status, circular remaining-time indicator, and upcoming events.
- Built-in light and dark theme support, with a runtime toggle and `UI_THEME=dark|light|auto` config.
- Built-in mock-data mode for kiosk preview before any provider is connected.
- Google Calendar integration using OAuth and the Calendar API.
- Outlook/Microsoft 365 integration through Microsoft Graph.
- Zoom upcoming meetings integration through Zoom OAuth.
- Deduplication of mirrored events that appear in more than one provider.
- A single systemd service for the kiosk dashboard, plus an optional setup-only OAuth server.

## Local run

1. Copy [.env.example](c:/Users/varog/source/copilot prompts/raspberry-pi/busy-time-device/.env.example) to `.env` and fill in the provider credentials.
2. Create a virtual environment and install dependencies.
3. Run:

```bash
python -m app.main
```

4. The dashboard starts in a window by default. Set `FULLSCREEN_MODE=1` if you want fullscreen locally.
5. Set `UI_THEME=light`, `UI_THEME=dark`, or `UI_THEME=auto` in `.env` to choose the theme. The UI also includes a theme toggle button.

## Provider setup

Run the setup server only when you need to connect or reconnect providers:

```bash
python -m flask --app app.auth_server run --host=0.0.0.0 --port=8080
```

Then open `http://127.0.0.1:8080` and use the connect links for Google, Microsoft, or Zoom.

## Mock preview mode

Set `MOCK_DATA_MODE=1` in `.env` to force the UI into a realistic preview state with:

- an active Zoom meeting with 45 minutes left,
- a focus block immediately after it,
- a follow-up project sync after the focus block.

This is useful for validating the portrait layout and kiosk startup before OAuth credentials are ready.

## Exporting a Preview Image

You can render the exact Qt dashboard to a PNG without starting the kiosk loop:

```bash
QT_QPA_PLATFORM=offscreen python -m app.main --export-preview data/preview.png
```

This is useful for remote review and for checking layout changes against the Pi's portrait resolution.

## Raspberry Pi deployment

From the Pi, copy this project to `/opt/chronopi-app`, create `/opt/chronopi-app/.env`, then run:

```bash
chmod +x /opt/chronopi-app/deploy/install_pi.sh
/opt/chronopi-app/deploy/install_pi.sh /opt/chronopi-app
```

This installs Python dependencies, registers `deploy/chronopi.service`, and starts the fullscreen Qt dashboard.

The app enforces a portrait layout even on a 480x320 panel. The framebuffer launcher defaults to `linuxfb:rotation=90`, while the Qt window itself always sizes and renders in portrait.

If you need to connect providers after deployment, run this once on the Pi:

```bash
cd /opt/chronopi-app
.venv/bin/python -m flask --app app.auth_server run --host=0.0.0.0 --port=8080
```

## Credentials and provider setup

### Google Calendar

1. Open Google Cloud Console.
2. Create a project or select an existing one.
3. Enable `Google Calendar API`.
4. Go to `APIs & Services` -> `OAuth consent screen` and configure an External app.
5. Add yourself as a test user if the app is not published.
6. Go to `Credentials` -> `Create credentials` -> `OAuth client ID`.
7. Choose `Web application`.
8. Add an authorized redirect URI: `http://PI_IP:8080/auth/google/callback`.
9. Copy the client ID and secret into `.env` as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.
10. Optionally set `GOOGLE_CALENDAR_ID` if you do not want the primary calendar.

### Outlook / Microsoft 365

1. Open Microsoft Entra admin center.
2. Go to `Applications` -> `App registrations` -> `New registration`.
3. Set the redirect URI to `Web` and enter `http://PI_IP:8080/auth/microsoft/callback`.
4. Under `API permissions`, add delegated permissions `User.Read`, `Calendars.Read`, and `offline_access`.
5. Grant consent if your tenant requires admin approval.
6. Under `Certificates & secrets`, create a client secret.
7. Copy the application client ID, secret, and tenant ID into `.env` as `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, and `MICROSOFT_TENANT_ID`.
8. Use `common` as the tenant ID if you want to sign in with a personal Microsoft account.

### Zoom

1. Open Zoom App Marketplace.
2. Create an `OAuth` app for user-level access.
3. Add redirect URL `http://PI_IP:8080/auth/zoom/callback`.
4. Add scopes for reading meetings. The exact scope names can change in Zoom Marketplace, but include read access for scheduled meetings and user profile basics.
5. Copy the Zoom client ID and secret into `.env` as `ZOOM_CLIENT_ID` and `ZOOM_CLIENT_SECRET`.
6. Complete the app activation flow inside Zoom Marketplace before authorizing from the Pi.

## Notes

- Set `APP_BASE_URL` in `.env` to the Pi address you will actually use during OAuth, for example `http://192.168.100.54:8080`.
- Use `SCREEN_ROTATION=right` to explicitly force portrait orientation in the kiosk launcher.
- For a 480x320 physical panel, keep `SCREEN_WIDTH=480` and `SCREEN_HEIGHT=320`; the app will render as portrait automatically.
- If your TFT is exposed as `/dev/fb1`, set `FRAMEBUFFER_DEVICE=/dev/fb1` so the Qt linuxfb backend renders to the panel instead of HDMI.
- Set `FULLSCREEN_MODE=1` on the Pi. The deployment launcher already exports it by default.
- Tokens are stored in `data/tokens.json` on the device.
- If the same meeting exists in more than one source, the app merges it into a single card when title and time range match.
- Zoom meetings are shown directly from Zoom; calendar meetings with Zoom links usually already appear through Google or Outlook as well.
