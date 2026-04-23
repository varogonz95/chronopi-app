# Chronopi

Chronopi is a portrait-oriented kiosk app for a Raspberry Pi with a TFT display. It merges upcoming availability from Google Calendar, Outlook/Microsoft 365, and Zoom into a single fullscreen dashboard designed around the supplied mockup.

## Why this stack

- Python keeps the data-provider and deployment story simple on a Raspberry Pi 3 A+.
- Qt renders the dashboard natively, which is materially lighter than keeping Chromium open all day.
- OAuth still runs on-device through a small setup server, so the Pi can refresh tokens and keep running independently.

## Features

- Fullscreen portrait dashboard with a minimal native Qt UI: one large current-status card, a divider, and one clear next-event card.
- Built-in light and dark theme support through `UI_THEME=dark|light|auto`.
- Built-in mock-data mode for kiosk preview before any provider is connected.
- Google Calendar integration using OAuth and the Calendar API.
- Outlook/Microsoft 365 integration through Microsoft Graph.
- Zoom upcoming meetings integration through Zoom OAuth.
- Deduplication of mirrored events that appear in more than one provider.
- A single systemd service for the kiosk dashboard, plus an optional setup-only OAuth server.

## Local run

1. Copy [.env.example](c:/Users/varog/source/copilot prompts/raspberry-pi/busy-time-device/.env.example) to `.env` and fill in the provider credentials.
2. Create a virtual environment and install dependencies from `requirements-pi.txt`.
3. Run:

```bash
python -m app.main
```

4. The dashboard starts in a window by default. Set `FULLSCREEN_MODE=1` if you want fullscreen locally.
5. Set `UI_THEME=light`, `UI_THEME=dark`, or `UI_THEME=auto` in `.env` to choose the theme.

## Provider setup

Run the setup server only when you need to connect or reconnect providers:

```bash
python -m flask --app app.auth_server run --host=0.0.0.0 --port=8080
```

Then open `http://127.0.0.1:8080` and use the connect links for Google, Microsoft, or Zoom.

## Azure Functions migration

You can move the setup server to Azure Functions without changing the Pi dashboard code path.

### What changed

- The repository root now includes [function_app.py](c:/Users/varog/source/copilot prompts/raspberry-pi/busy-time-device/function_app.py) and [host.json](c:/Users/varog/source/copilot prompts/raspberry-pi/busy-time-device/host.json) for an HTTP-triggered Azure Functions app.
- Token storage now supports either a local file or Azure Blob Storage.
- The Flask setup server and the Azure Functions app use the same shared OAuth logic.

### Shared token storage

If Azure handles OAuth and the Pi renders the dashboard, both environments must point at the same token store.

- Keep `TOKEN_STORE_BACKEND=file` to store tokens locally in `data/tokens.json`.
- Set `TOKEN_STORE_BACKEND=azure_blob` to store tokens in Azure Blob Storage.
- When using Azure Blob, set `AZURE_STORAGE_CONNECTION_STRING`, `TOKEN_STORE_CONTAINER`, and `TOKEN_STORE_BLOB` in both Azure Functions configuration and the Pi `.env` file.

### Pi configuration for Azure auth

Set these on the Pi so the dashboard reads tokens from Azure and the setup links point to the Function App:

```env
APP_BASE_URL=https://YOUR_FUNCTION_APP.azurewebsites.net
TOKEN_STORE_BACKEND=azure_blob
AZURE_STORAGE_CONNECTION_STRING=...
TOKEN_STORE_CONTAINER=chronopi
TOKEN_STORE_BLOB=tokens.json
```

### Deploy the Function App

1. Create an Azure Function App for Python.
2. Use the same Python runtime as this repo's Azure deployment package. The workflow pins Azure to Python 3.11, and the Function App should not be left on Python 3.13 if you are using `azure-storage-blob`.
2. Set app settings from [local.settings.example.json](c:/Users/varog/source/copilot prompts/raspberry-pi/busy-time-device/local.settings.example.json).
3. Set `APP_BASE_URL` to the public Function App URL.
4. Register your Google, Microsoft, and Zoom redirect URIs against that Azure URL, for example `https://YOUR_FUNCTION_APP.azurewebsites.net/auth/google/callback`.
5. Deploy this repository root to Azure Functions.

If the Function App is already deployed and the invocation logs show `ModuleNotFoundError: No module named '_cffi_backend'`, check the Function App runtime stack first. That error usually means Azure is running a newer Python version than the one used to build `.python_packages`, so the blob-storage dependency chain is loading incompatible native wheels.

### Local Azure Functions run

1. Copy `local.settings.example.json` to `local.settings.json`.
2. Install the Azure runtime dependencies from `requirements.txt`.
3. Start the function app with Azure Functions Core Tools.

## Mock preview mode

Set `MOCK_DATA_MODE=1` in `.env` to force the UI into a realistic preview state with:

- an active Zoom meeting with 45 minutes left,
- a focus block immediately after it,
- a follow-up project sync after the focus block.

This is useful for validating the simplified portrait layout and kiosk startup before OAuth credentials are ready.

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

- Set `APP_BASE_URL` in `.env` to the URL that handles OAuth, either the Pi auth server or the Azure Function App.
- Use `SCREEN_ROTATION=right` to explicitly force portrait orientation in the kiosk launcher.
- For a 480x320 physical panel, keep `SCREEN_WIDTH=480` and `SCREEN_HEIGHT=320`; the app will render as portrait automatically.
- If your TFT is exposed as `/dev/fb1`, set `FRAMEBUFFER_DEVICE=/dev/fb1` so the Qt linuxfb backend renders to the panel instead of HDMI.
- Set `FULLSCREEN_MODE=1` on the Pi. The deployment launcher already exports it by default.
- Tokens are stored either in `data/tokens.json` or in Azure Blob Storage, depending on `TOKEN_STORE_BACKEND`.
- If the same meeting exists in more than one source, the app merges it into a single card when title and time range match.
- Zoom meetings are shown directly from Zoom; calendar meetings with Zoom links usually already appear through Google or Outlook as well.
