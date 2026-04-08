from __future__ import annotations

from datetime import datetime, timedelta
from math import ceil
from typing import Any

from .config import Settings
from .models import CalendarEvent
from .providers import OAuthProviderBase


def format_clock(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0")


def format_date(dt: datetime) -> str:
    return dt.strftime("%A, %b %d")


def format_range(event: CalendarEvent) -> str:
    return f"{format_clock(event.starts_at)} to {format_clock(event.ends_at)}"


def build_mock_events(now: datetime) -> list[CalendarEvent]:
    meeting_start = now.replace(second=0, microsecond=0) - timedelta(
        minutes=15
    )
    meeting_end = meeting_start + timedelta(hours=1)
    focus_start = meeting_end
    focus_end = focus_start + timedelta(minutes=30)
    sync_start = focus_end
    sync_end = sync_start + timedelta(minutes=30)

    return [
        CalendarEvent(
            source="mock",
            source_id="client-call",
            title="Client Call",
            starts_at=meeting_start,
            ends_at=meeting_end,
            location="Via Zoom",
            description="Preview event for kiosk layout validation.",
            join_url="https://zoom.us/mock-call",
        ),
        CalendarEvent(
            source="mock",
            source_id="focus-time",
            title="Focus Time",
            starts_at=focus_start,
            ends_at=focus_end,
            location="Heads-down work",
            description="Preview focus block.",
            is_focus=True,
        ),
        CalendarEvent(
            source="mock",
            source_id="project-sync",
            title="Project Sync",
            starts_at=sync_start,
            ends_at=sync_end,
            location="Team room",
            description="Preview follow-up meeting.",
        ),
    ]


def dedupe_events(events: list[CalendarEvent]) -> list[CalendarEvent]:
    merged: dict[tuple[str, str, str], CalendarEvent] = {}
    for event in sorted(events, key=lambda item: item.starts_at):
        key = (
            " ".join(event.title.lower().split()),
            event.starts_at.replace(second=0, microsecond=0).isoformat(),
            event.ends_at.replace(second=0, microsecond=0).isoformat(),
        )
        existing = merged.get(key)
        if not existing:
            merged[key] = event
            continue
        for source in event.sources:
            if source not in existing.sources:
                existing.sources.append(source)
        if not existing.location and event.location:
            existing.location = event.location
        if not existing.join_url and event.join_url:
            existing.join_url = event.join_url
        if not existing.description and event.description:
            existing.description = event.description
        existing.is_focus = existing.is_focus or event.is_focus
    return list(merged.values())


def current_and_next(
    events: list[CalendarEvent],
    now: datetime,
) -> tuple[CalendarEvent | None, CalendarEvent | None, list[CalendarEvent]]:
    current = None
    future: list[CalendarEvent] = []
    for event in events:
        if event.starts_at <= now < event.ends_at and current is None:
            current = event
            continue
        if event.ends_at > now:
            future.append(event)
    next_event = future[0] if future else None
    upcoming = [
        item
        for item in future
        if current is None or item.source_id != current.source_id
    ]
    return current, next_event, upcoming


def build_view_model(
    events: list[CalendarEvent],
    now: datetime,
) -> dict[str, Any]:
    current, next_event, upcoming = current_and_next(events, now)

    if current:
        total_seconds = max(
            (current.ends_at - current.starts_at).total_seconds(),
            1,
        )
        remaining_seconds = max((current.ends_at - now).total_seconds(), 0)
        remaining_minutes = ceil(remaining_seconds / 60)
        heading = "Focus time" if current.is_focus else "In a meeting"
        subheading = f"From {format_range(current)}"
        ring_label = "min left"
        progress = remaining_seconds / total_seconds
        current_title = current.title
        current_subtitle = current.subtitle
    else:
        if next_event:
            free_seconds = max((next_event.starts_at - now).total_seconds(), 0)
            remaining_minutes = ceil(free_seconds / 60)
            heading = "Available"
            subheading = f"Free until {format_clock(next_event.starts_at)}"
            ring_label = "min free"
            progress = 1.0
            current_title = "Available now"
            current_subtitle = f"Next: {next_event.title}"
        else:
            remaining_minutes = 0
            heading = "Available"
            subheading = "No more events today"
            ring_label = "clear"
            progress = 1.0
            current_title = "Available now"
            current_subtitle = "Calendar is clear"

    next_summary = None
    if next_event and (
        current is None or next_event.source_id != current.source_id
    ):
        next_summary = {
            "title": next_event.title,
            "range": format_range(next_event),
        }

    return {
        "generatedAt": now.isoformat(),
        "clock": format_clock(now),
        "dateLabel": format_date(now),
        "heading": heading,
        "subheading": subheading,
        "remainingMinutes": remaining_minutes,
        "ringLabel": ring_label,
        "progress": round(max(0.0, min(progress, 1.0)), 4),
        "currentTitle": current_title,
        "currentSubtitle": current_subtitle,
        "currentEvent": current.to_dict() if current else None,
        "nextEvent": next_summary,
        "upcoming": [
            {
                "title": event.title,
                "subtitle": event.subtitle,
                "range": format_range(event),
                "kind": event.kind,
            }
            for event in upcoming[:4]
        ],
    }


def collect_events(
    settings: Settings,
    providers: dict[str, OAuthProviderBase],
    now: datetime,
) -> tuple[list[CalendarEvent], list[str], bool]:
    if settings.mock_data_mode:
        events = sorted(
            build_mock_events(now),
            key=lambda item: item.starts_at,
        )
        return events, [], True

    all_events: list[CalendarEvent] = []
    errors: list[str] = []
    for provider in providers.values():
        if not provider.is_configured() or not provider.is_connected():
            continue
        try:
            all_events.extend(
                provider.fetch_events(now, settings.lookahead_hours)
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{provider.display_name}: {exc}")
    events = sorted(dedupe_events(all_events), key=lambda item: item.starts_at)
    return events, errors, False


def provider_status(
    providers: dict[str, OAuthProviderBase],
) -> list[dict[str, Any]]:
    return [provider.provider_status() for provider in providers.values()]


def build_status_payload(
    settings: Settings,
    providers: dict[str, OAuthProviderBase],
) -> dict[str, Any]:
    now = datetime.now(settings.timezone)
    events, errors, using_mock = collect_events(settings, providers, now)
    payload = build_view_model(events, now)
    payload["providers"] = provider_status(providers)
    payload["errors"] = errors
    payload["mockMode"] = using_mock
    payload["setupUrl"] = settings.base_url
    return payload
