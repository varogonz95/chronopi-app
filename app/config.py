from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo
import os


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    base_url: str
    timezone_name: str
    secret_key: str
    lookahead_hours: int
    refresh_seconds: int
    mock_data_mode: bool
    token_store_path: Path
    google_client_id: str
    google_client_secret: str
    google_calendar_id: str
    microsoft_client_id: str
    microsoft_client_secret: str
    microsoft_tenant_id: str
    zoom_client_id: str
    zoom_client_secret: str
    ui_label: str
    ui_sublabel: str
    ui_theme: str
    screen_width: int
    screen_height: int
    fullscreen_mode: bool

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    @staticmethod
    def _env_flag(name: str, default: str = "0") -> bool:
        return os.getenv(name, default).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            host=os.getenv("APP_HOST", "0.0.0.0"),
            port=int(os.getenv("APP_PORT", "8080")),
            base_url=os.getenv(
                "APP_BASE_URL",
                "http://127.0.0.1:8080",
            ).rstrip("/"),
            timezone_name=os.getenv("APP_TIMEZONE", "UTC"),
            secret_key=os.getenv("APP_SECRET_KEY", "change-me"),
            lookahead_hours=int(os.getenv("LOOKAHEAD_HOURS", "12")),
            refresh_seconds=max(
                15,
                int(os.getenv("REFRESH_SECONDS", "30")),
            ),
            mock_data_mode=cls._env_flag("MOCK_DATA_MODE", "0"),
            token_store_path=Path(
                os.getenv("TOKEN_STORE_PATH", "data/tokens.json")
            ),
            google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
            google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
            google_calendar_id=os.getenv("GOOGLE_CALENDAR_ID", "primary"),
            microsoft_client_id=os.getenv("MICROSOFT_CLIENT_ID", ""),
            microsoft_client_secret=os.getenv("MICROSOFT_CLIENT_SECRET", ""),
            microsoft_tenant_id=os.getenv("MICROSOFT_TENANT_ID", "common"),
            zoom_client_id=os.getenv("ZOOM_CLIENT_ID", ""),
            zoom_client_secret=os.getenv("ZOOM_CLIENT_SECRET", ""),
            ui_label=os.getenv("UI_LABEL", "Availability Board"),
            ui_sublabel=os.getenv("UI_SUBLABEL", "Home Office"),
            ui_theme=os.getenv("UI_THEME", "dark").strip().lower(),
            screen_width=int(os.getenv("SCREEN_WIDTH", "480")),
            screen_height=int(os.getenv("SCREEN_HEIGHT", "320")),
            fullscreen_mode=cls._env_flag("FULLSCREEN_MODE", "0"),
        )
