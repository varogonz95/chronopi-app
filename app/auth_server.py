from __future__ import annotations

import os

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, request

from .auth_logic import (
    build_oauth_state,
    oauth_state_error,
    render_setup_page,
    should_accept_callback,
)
from .config import Settings
from .dashboard import provider_status
from .providers import build_provider_registry, create_token_store

load_dotenv()

settings = Settings.from_env()
token_store = create_token_store(settings)
providers = build_provider_registry(settings, token_store)
app = Flask(__name__)
app.secret_key = settings.secret_key


@app.route("/")
def index():
    statuses = provider_status(providers)
    return render_setup_page(statuses)


@app.route("/api/providers")
def api_providers():
    return jsonify({"providers": provider_status(providers)})


@app.route("/auth/<provider_name>/start")
def auth_start(provider_name: str):
    provider = providers.get(provider_name)
    if provider is None or not provider.is_configured():
        abort(404)
    state = build_oauth_state(settings.secret_key, provider_name)
    return redirect(provider.build_auth_url(state))


@app.route("/auth/<provider_name>/callback")
def auth_callback(provider_name: str):
    provider = providers.get(provider_name)
    if provider is None or not provider.is_configured():
        abort(404)
    actual_state = request.args.get("state")
    code = request.args.get("code")
    if not should_accept_callback(
        settings.secret_key,
        provider_name,
        actual_state,
        code,
    ):
        app.logger.warning(
            "OAuth state validation failed for %s: %s",
            provider_name,
            oauth_state_error(
                settings.secret_key,
                provider_name,
                actual_state,
            ),
        )
        abort(400, description="OAuth state mismatch")
    if provider_name == "zoom" and not actual_state and code:
        app.logger.warning(
            "Zoom callback missing state; accepting code-only callback"
        )
    if request.args.get("error"):
        description = (
            request.args.get("error_description") or request.args["error"]
        )
        abort(400, description=description)
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
