from __future__ import annotations

import json
import logging

import azure.functions as func

from app.auth_logic import (
    build_oauth_state,
    oauth_state_error,
    render_setup_page,
    should_accept_callback,
)
from app.config import Settings
from app.dashboard import provider_status
from app.providers import build_provider_registry, create_token_store

settings = Settings.from_env()
token_store = create_token_store(settings)
providers = build_provider_registry(settings, token_store)
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
logger = logging.getLogger("chronopi.azure_auth")


def redirect_response(location: str) -> func.HttpResponse:
    return func.HttpResponse(status_code=302, headers={"Location": location})


@app.route(route="", methods=["GET"])
def index(req: func.HttpRequest) -> func.HttpResponse:
    del req
    statuses = provider_status(providers)
    return func.HttpResponse(
        render_setup_page(statuses),
        mimetype="text/html",
        status_code=200,
    )


@app.route(route="api/providers", methods=["GET"])
def api_providers(req: func.HttpRequest) -> func.HttpResponse:
    del req
    return func.HttpResponse(
        json.dumps({"providers": provider_status(providers)}),
        mimetype="application/json",
        status_code=200,
    )


@app.route(route="auth/{provider_name}/start", methods=["GET"])
def auth_start(req: func.HttpRequest) -> func.HttpResponse:
    provider_name = req.route_params.get("provider_name", "")
    provider = providers.get(provider_name)
    if provider is None or not provider.is_configured():
        return func.HttpResponse(status_code=404)
    state = build_oauth_state(settings.secret_key, provider_name)
    return redirect_response(provider.build_auth_url(state))


@app.route(route="auth/{provider_name}/callback", methods=["GET"])
def auth_callback(req: func.HttpRequest) -> func.HttpResponse:
    provider_name = req.route_params.get("provider_name", "")
    provider = providers.get(provider_name)
    if provider is None or not provider.is_configured():
        return func.HttpResponse(status_code=404)

    actual_state = req.params.get("state")
    code = req.params.get("code")
    if not should_accept_callback(
        settings.secret_key,
        provider_name,
        actual_state,
        code,
    ):
        logger.warning(
            "OAuth state validation failed for %s: %s",
            provider_name,
            oauth_state_error(
                settings.secret_key,
                provider_name,
                actual_state,
            ),
        )
        return func.HttpResponse("OAuth state mismatch", status_code=400)

    if provider_name == "zoom" and not actual_state and code:
        logger.warning(
            "Zoom callback missing state; accepting code-only callback"
        )

    error = req.params.get("error")
    if error:
        description = req.params.get("error_description") or error
        return func.HttpResponse(description, status_code=400)

    if not code:
        return func.HttpResponse(
            "Missing authorization code",
            status_code=400,
        )

    token_payload = provider.exchange_code(code)
    token_store.put(provider_name, token_payload)
    return redirect_response(f"{settings.base_url}/?connected={provider_name}")
