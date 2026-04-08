from __future__ import annotations

import html
import os

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, request, session

from .config import Settings
from .dashboard import provider_status
from .providers import TokenStore, build_provider_registry, generate_state

load_dotenv()

settings = Settings.from_env()
token_store = TokenStore(settings.token_store_path)
providers = build_provider_registry(settings, token_store)
app = Flask(__name__)
app.secret_key = settings.secret_key


@app.route("/")
def index():
    statuses = provider_status(providers)
    rows = []
    for provider in statuses:
        state = "connected" if provider["connected"] else "not connected"
        action = ""
        if provider["configured"]:
            action = (
                f'<a href="{html.escape(provider["connectUrl"])}">Connect</a>'
            )
        rows.append(
            "<li>"
            f"<strong>{html.escape(provider['displayName'])}</strong>: {state}"
            f" {action}"
            "</li>"
        )

    return (
        "<html><body style=\"font-family:sans-serif;padding:24px;\">"
        "<h1>Busy Time Setup</h1>"
        "<p>This setup server is only needed when connecting or reconnecting "
        "providers.</p>"
        "<ul>"
        + "".join(rows)
        + "</ul>"
        "</body></html>"
    )


@app.route("/api/providers")
def api_providers():
    return jsonify({"providers": provider_status(providers)})


@app.route("/auth/<provider_name>/start")
def auth_start(provider_name: str):
    provider = providers.get(provider_name)
    if provider is None or not provider.is_configured():
        abort(404)
    state = generate_state()
    session[f"oauth_state:{provider_name}"] = state
    return redirect(provider.build_auth_url(state))


@app.route("/auth/<provider_name>/callback")
def auth_callback(provider_name: str):
    provider = providers.get(provider_name)
    if provider is None or not provider.is_configured():
        abort(404)
    expected_state = session.pop(f"oauth_state:{provider_name}", None)
    actual_state = request.args.get("state")
    if not expected_state or actual_state != expected_state:
        abort(400, description="OAuth state mismatch")
    if request.args.get("error"):
        description = (
            request.args.get("error_description") or request.args["error"]
        )
        abort(400, description=description)
    code = request.args.get("code")
    if not code:
        abort(400, description="Missing authorization code")
    token_payload = provider.exchange_code(code)
    token_store.put(provider_name, token_payload)
    return redirect("/?connected=" + provider_name)


if __name__ == "__main__":
    app.run(
        host=settings.host,
        port=settings.port,
        debug=os.getenv("FLASK_DEBUG") == "1",
    )
