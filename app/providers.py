from __future__ import annotations

from base64 import b64encode
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
import json
import secrets

import httpx
from dateutil.parser import isoparse

from .config import Settings
from .models import CalendarEvent


class TokenStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, payload: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get(self, provider_name: str) -> dict[str, Any] | None:
        return self.load().get(provider_name)

    def put(self, provider_name: str, token_payload: dict[str, Any]) -> None:
        payload = self.load()
        payload[provider_name] = token_payload
        self.save(payload)


def parse_datetime(value: str, timezone) -> datetime:
    parsed = isoparse(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone)


class OAuthProviderBase:
    name = "base"
    display_name = "Base"
    auth_url = ""
    token_url = ""
    scopes: list[str] = []

    def __init__(self, settings: Settings, token_store: TokenStore) -> None:
        self.settings = settings
        self.token_store = token_store

    @property
    def redirect_uri(self) -> str:
        return f"{self.settings.base_url}/auth/{self.name}/callback"

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def is_connected(self) -> bool:
        return bool(self.token_store.get(self.name))

    @property
    def client_id(self) -> str:
        raise NotImplementedError

    @property
    def client_secret(self) -> str:
        raise NotImplementedError

    def build_auth_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": state,
        }
        if self.scopes:
            params["scope"] = " ".join(self.scopes)
        return f"{self.auth_url}?{urlencode(params)}"

    def exchange_code(self, code: str) -> dict[str, Any]:
        raise NotImplementedError

    def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        raise NotImplementedError

    def token_payload(self) -> dict[str, Any]:
        token = self.token_store.get(self.name)
        if not token:
            raise RuntimeError(f"{self.display_name} is not connected")

        expires_at = token.get("expires_at")
        if expires_at:
            expiry = datetime.fromisoformat(expires_at)
            if expiry <= datetime.now(UTC) + timedelta(minutes=2):
                refreshed = self.refresh_access_token(token["refresh_token"])
                self.token_store.put(self.name, refreshed)
                return refreshed
        return token

    def access_token(self) -> str:
        return self.token_payload()["access_token"]

    def _token_from_response(
        self,
        response_payload: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "access_token": response_payload["access_token"],
            "refresh_token": response_payload.get("refresh_token"),
            "token_type": response_payload.get("token_type", "Bearer"),
        }
        expires_in = int(response_payload.get("expires_in", 3600))
        payload["expires_at"] = (
            datetime.now(UTC) + timedelta(seconds=expires_in)
        ).isoformat()
        return payload

    def provider_status(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "displayName": self.display_name,
            "configured": self.is_configured(),
            "connected": self.is_connected(),
            "connectUrl": f"/auth/{self.name}/start",
        }

    def fetch_events(
        self,
        now: datetime,
        lookahead_hours: int,
    ) -> list[CalendarEvent]:
        raise NotImplementedError


class GoogleCalendarProvider(OAuthProviderBase):
    name = "google"
    display_name = "Google Calendar"
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    scopes = [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/calendar.readonly",
    ]

    @property
    def client_id(self) -> str:
        return self.settings.google_client_id

    @property
    def client_secret(self) -> str:
        return self.settings.google_client_secret

    def build_auth_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": state,
            "scope": " ".join(self.scopes),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }
        return f"{self.auth_url}?{urlencode(params)}"

    def exchange_code(self, code: str) -> dict[str, Any]:
        response = httpx.post(
            self.token_url,
            data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=30,
        )
        response.raise_for_status()
        return self._token_from_response(response.json())

    def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        response = httpx.post(
            self.token_url,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = self._token_from_response(response.json())
        payload["refresh_token"] = response.json().get(
            "refresh_token",
            refresh_token,
        )
        return payload

    def fetch_events(
        self,
        now: datetime,
        lookahead_hours: int,
    ) -> list[CalendarEvent]:
        events_url = (
            "https://www.googleapis.com/calendar/v3/calendars/"
            f"{self.settings.google_calendar_id}/events"
        )
        time_max = (
            now + timedelta(hours=lookahead_hours)
        ).astimezone(UTC).isoformat()
        response = httpx.get(
            events_url,
            params={
                "timeMin": now.astimezone(UTC).isoformat(),
                "timeMax": time_max,
                "singleEvents": "true",
                "orderBy": "startTime",
            },
            headers={"Authorization": f"Bearer {self.access_token()}"},
            timeout=30,
        )
        response.raise_for_status()
        events = []
        for item in response.json().get("items", []):
            if item.get("status") == "cancelled":
                continue
            if "date" in item.get("start", {}):
                continue
            title = item.get("summary") or "Busy"
            starts_at = parse_datetime(
                item["start"]["dateTime"],
                self.settings.timezone,
            )
            ends_at = parse_datetime(
                item["end"]["dateTime"],
                self.settings.timezone,
            )
            events.append(
                CalendarEvent(
                    source=self.name,
                    source_id=item["id"],
                    title=title,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    location=item.get("location", ""),
                    description=item.get("description", ""),
                    is_focus=(
                        item.get("eventType") == "focusTime"
                        or "focus" in title.lower()
                    ),
                    join_url=item.get("hangoutLink"),
                )
            )
        return events


class MicrosoftGraphProvider(OAuthProviderBase):
    name = "microsoft"
    display_name = "Outlook"
    scopes = ["offline_access", "User.Read", "Calendars.Read"]

    @property
    def auth_url(self) -> str:  # type: ignore[override]
        tenant_id = self.settings.microsoft_tenant_id
        return (
            "https://login.microsoftonline.com/"
            f"{tenant_id}/oauth2/v2.0/authorize"
        )

    @property
    def token_url(self) -> str:  # type: ignore[override]
        tenant_id = self.settings.microsoft_tenant_id
        return (
            "https://login.microsoftonline.com/"
            f"{tenant_id}/oauth2/v2.0/token"
        )

    @property
    def client_id(self) -> str:
        return self.settings.microsoft_client_id

    @property
    def client_secret(self) -> str:
        return self.settings.microsoft_client_secret

    def exchange_code(self, code: str) -> dict[str, Any]:
        response = httpx.post(
            self.token_url,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
                "scope": " ".join(self.scopes),
            },
            timeout=30,
        )
        response.raise_for_status()
        return self._token_from_response(response.json())

    def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        response = httpx.post(
            self.token_url,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": " ".join(self.scopes),
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = self._token_from_response(response.json())
        payload["refresh_token"] = response.json().get(
            "refresh_token",
            refresh_token,
        )
        return payload

    def fetch_events(
        self,
        now: datetime,
        lookahead_hours: int,
    ) -> list[CalendarEvent]:
        end_time = (
            now + timedelta(hours=lookahead_hours)
        ).astimezone(UTC).isoformat()
        response = httpx.get(
            "https://graph.microsoft.com/v1.0/me/calendarView",
            params={
                "startDateTime": now.astimezone(UTC).isoformat(),
                "endDateTime": end_time,
            },
            headers={
                "Authorization": f"Bearer {self.access_token()}",
                "Prefer": 'outlook.timezone="UTC"',
            },
            timeout=30,
        )
        response.raise_for_status()
        events = []
        for item in response.json().get("value", []):
            starts_at = parse_datetime(
                item["start"]["dateTime"],
                UTC,
            ).astimezone(self.settings.timezone)
            ends_at = parse_datetime(
                item["end"]["dateTime"],
                UTC,
            ).astimezone(self.settings.timezone)
            if item.get("isAllDay"):
                continue
            title = item.get("subject") or "Busy"
            location = item.get("location", {}).get("displayName", "")
            join_url = item.get("onlineMeeting", {}).get("joinUrl")
            show_as = (item.get("showAs") or "").lower()
            events.append(
                CalendarEvent(
                    source=self.name,
                    source_id=item["id"],
                    title=title,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    location=location,
                    description=item.get("bodyPreview", ""),
                    is_focus=(
                        show_as == "workingelsewhere"
                        or "focus" in title.lower()
                    ),
                    join_url=join_url,
                )
            )
        return events


class ZoomProvider(OAuthProviderBase):
    name = "zoom"
    display_name = "Zoom"
    auth_url = "https://zoom.us/oauth/authorize"
    token_url = "https://zoom.us/oauth/token"

    @property
    def client_id(self) -> str:
        return self.settings.zoom_client_id

    @property
    def client_secret(self) -> str:
        return self.settings.zoom_client_secret

    def build_auth_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": state,
        }
        return f"{self.auth_url}?{urlencode(params)}"

    def _basic_auth_header(self) -> dict[str, str]:
        credentials = f"{self.client_id}:{self.client_secret}"
        token = b64encode(credentials.encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {token}"}

    def exchange_code(self, code: str) -> dict[str, Any]:
        response = httpx.post(
            self.token_url,
            params={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
            },
            headers=self._basic_auth_header(),
            timeout=30,
        )
        response.raise_for_status()
        return self._token_from_response(response.json())

    def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        response = httpx.post(
            self.token_url,
            params={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers=self._basic_auth_header(),
            timeout=30,
        )
        response.raise_for_status()
        payload = self._token_from_response(response.json())
        payload["refresh_token"] = response.json().get(
            "refresh_token",
            refresh_token,
        )
        return payload

    def fetch_events(
        self,
        now: datetime,
        lookahead_hours: int,
    ) -> list[CalendarEvent]:
        response = httpx.get(
            "https://api.zoom.us/v2/users/me/meetings",
            params={"type": "upcoming", "page_size": 30},
            headers={"Authorization": f"Bearer {self.access_token()}"},
            timeout=30,
        )
        response.raise_for_status()
        horizon = now + timedelta(hours=lookahead_hours)
        events = []
        for item in response.json().get("meetings", []):
            if not item.get("start_time"):
                continue
            starts_at = parse_datetime(
                item["start_time"],
                self.settings.timezone,
            )
            duration = int(item.get("duration") or 0)
            ends_at = starts_at + timedelta(minutes=duration)
            if ends_at < now or starts_at > horizon:
                continue
            events.append(
                CalendarEvent(
                    source=self.name,
                    source_id=str(item["id"]),
                    title=item.get("topic") or "Zoom Meeting",
                    starts_at=starts_at,
                    ends_at=ends_at,
                    location="Via Zoom",
                    description=item.get("agenda", ""),
                    join_url=item.get("join_url"),
                )
            )
        return events


def build_provider_registry(
    settings: Settings,
    token_store: TokenStore,
) -> dict[str, OAuthProviderBase]:
    providers: list[OAuthProviderBase] = [
        GoogleCalendarProvider(settings, token_store),
        MicrosoftGraphProvider(settings, token_store),
        ZoomProvider(settings, token_store),
    ]
    return {provider.name: provider for provider in providers}


def generate_state() -> str:
    return secrets.token_urlsafe(24)
