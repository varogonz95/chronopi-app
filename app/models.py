from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CalendarEvent:
    source: str
    source_id: str
    title: str
    starts_at: datetime
    ends_at: datetime
    location: str = ""
    description: str = ""
    is_focus: bool = False
    join_url: str | None = None
    sources: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.sources:
            self.sources = [self.source]

    @property
    def duration_minutes(self) -> int:
        duration = (self.ends_at - self.starts_at).total_seconds() // 60
        return max(0, int(duration))

    @property
    def kind(self) -> str:
        return "focus" if self.is_focus else "meeting"

    @property
    def subtitle(self) -> str:
        if self.location:
            return self.location
        if self.join_url and "zoom" in self.join_url.lower():
            return "Via Zoom"
        source_names = {
            "google": "Google Calendar",
            "microsoft": "Outlook",
            "zoom": "Zoom",
        }
        unique_sources = []
        for source in self.sources:
            label = source_names.get(source, source.title())
            if label not in unique_sources:
                unique_sources.append(label)
        return " + ".join(unique_sources)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": f"{self.source}:{self.source_id}",
            "title": self.title,
            "subtitle": self.subtitle,
            "kind": self.kind,
            "startsAt": self.starts_at.isoformat(),
            "endsAt": self.ends_at.isoformat(),
            "durationMinutes": self.duration_minutes,
            "joinUrl": self.join_url,
            "sources": self.sources,
        }
