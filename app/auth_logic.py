from __future__ import annotations

import html
from typing import Any

from itsdangerous import BadSignature, URLSafeSerializer

from .providers import generate_state


def _state_serializer(secret_key: str) -> URLSafeSerializer:
    return URLSafeSerializer(secret_key, salt="oauth-state")


def build_oauth_state(secret_key: str, provider_name: str) -> str:
    return _state_serializer(secret_key).dumps(
        {
            "provider": provider_name,
            "nonce": generate_state(),
        }
    )


def is_valid_oauth_state(
    secret_key: str,
    provider_name: str,
    state: str | None,
) -> bool:
    if not state:
        return False
    try:
        payload = _state_serializer(secret_key).loads(state)
    except BadSignature:
        return False
    return payload.get("provider") == provider_name and bool(
        payload.get("nonce")
    )


def oauth_state_error(
    secret_key: str,
    provider_name: str,
    state: str | None,
) -> str:
    if not state:
        return "missing state query parameter"
    try:
        payload = _state_serializer(secret_key).loads(state)
    except BadSignature:
        return "invalid or tampered state signature"
    if payload.get("provider") != provider_name:
        return "state provider does not match callback provider"
    if not payload.get("nonce"):
        return "state nonce missing"
    return "unknown state validation error"


def should_accept_callback(
    secret_key: str,
    provider_name: str,
    state: str | None,
    code: str | None,
) -> bool:
    if is_valid_oauth_state(secret_key, provider_name, state):
        return True
    return provider_name == "zoom" and not state and bool(code)


def render_setup_page(statuses: list[dict[str, Any]]) -> str:
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
        "<h1>Chronopi Setup</h1>"
        "<p>This setup server is only needed when connecting or reconnecting "
        "providers.</p>"
        "<ul>"
        + "".join(rows)
        + "</ul>"
        "</body></html>"
    )
