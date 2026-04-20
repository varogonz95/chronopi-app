from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import os
from pathlib import Path
import sys
from typing import Any, cast

try:
    from dotenv import load_dotenv
except ImportError:
    def _load_dotenv_fallback(*args, **kwargs) -> bool:
        del args, kwargs
        return False

    load_dotenv = _load_dotenv_fallback
from PySide6.QtCore import (
    QEvent,
    QObject,
    QRectF,
    QRunnable,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .config import Settings
from .dashboard import build_status_payload
from .providers import build_provider_registry, create_token_store

load_dotenv()

settings = Settings.from_env()
token_store = create_token_store(settings)
providers = build_provider_registry(settings, token_store)
DEFAULT_FONT_FAMILY = "DejaVu Sans"
APP_FONT_FAMILY = DEFAULT_FONT_FAMILY
THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "background": "#111112",
        "meeting_top": "#f86c16",
        "meeting_bottom": "#ef4b05",
        "focus_top": "#eac569",
        "focus_bottom": "#d6a13f",
        "available_top": "#2ec769",
        "available_bottom": "#88c7ac",
        "hero_text": "#130d09",
        "hero_icon": "#ffc36d",
        "hero_meta": "rgba(19, 13, 9, 0.72)",
        "next_top": "#4a4a4c",
        "next_bottom": "#404042",
        "next_text": "#faf7f2",
        "next_muted": "#ece7df",
        "next_icon": "#faf7f2",
        "divider": "#f3f0eb",
    },
    "light": {
        "background": "#f4eee6",
        "meeting_top": "#f57b2f",
        "meeting_bottom": "#e86418",
        "focus_top": "#e2c97a",
        "focus_bottom": "#d0a852",
        "available_top": "#2ec769",
        "available_bottom": "#88c7ac",
        "hero_text": "#16100c",
        "hero_icon": "#ffe3a6",
        "hero_meta": "rgba(22, 16, 12, 0.70)",
        "next_top": "#dfd8d0",
        "next_bottom": "#d3cbc3",
        "next_text": "#1e1915",
        "next_muted": "#342d28",
        "next_icon": "#1e1915",
        "divider": "#1e1915",
    },
}

STATUS_PALETTES: dict[str, dict[str, str]] = {
    "available": {
        "page_bg": "#eaeced",
        "hero_bg": "#c8d3cf",
        "hero_text": "#111722",
        "hero_sub": "#2f3b46",
        "hero_muted": "#4f5b64",
        "badge_bg": "rgba(255,255,255,0.55)",
        "badge_dot": "#2f7d57",
        "chip_bg": "rgba(255,255,255,0.62)",
        "section_title": "#171d28",
        "section_cta": "#2f7d57",
        "item_bg": "#f3f4f6",
        "date_bg": "#ecd0d0",
        "date_text": "#321514",
        "tail_bg": "#e3e6ea",
        "tail_text": "#2a2f38",
        "error": "#a42f2f",
    },
    "busy": {
        "page_bg": "#eaeced",
        "hero_bg": "#f2dede",
        "hero_text": "#5a0707",
        "hero_sub": "#8c1f1f",
        "hero_muted": "#8c1f1f",
        "badge_bg": "rgba(255,255,255,0.52)",
        "badge_dot": "#bc2a2a",
        "chip_bg": "#f0dbdb",
        "section_title": "#171d28",
        "section_cta": "#bc2a2a",
        "item_bg": "#f3f4f6",
        "date_bg": "#d9dce1",
        "date_text": "#20252c",
        "tail_bg": "#e4e7eb",
        "tail_text": "#2d323a",
        "error": "#a42f2f",
    },
    "focus": {
        "page_bg": "#eaeced",
        "hero_bg": "#67577a",
        "hero_text": "#f7f4ff",
        "hero_sub": "#e6deef",
        "hero_muted": "#d8cee6",
        "badge_bg": "rgba(211,189,229,0.35)",
        "badge_dot": "#f5ecff",
        "chip_bg": "rgba(183,157,206,0.5)",
        "section_title": "#171d28",
        "section_cta": "#6d7570",
        "item_bg": "#f3f4f6",
        "date_bg": "#d4d7dc",
        "date_text": "#2e343c",
        "tail_bg": "#e4e7eb",
        "tail_text": "#2d323a",
        "error": "#a42f2f",
    },
    "ooo": {
        "page_bg": "#eaeced",
        "hero_bg": "#d2dae5",
        "hero_text": "#122140",
        "hero_sub": "#314b72",
        "hero_muted": "#3f5a80",
        "badge_bg": "rgba(255,255,255,0.46)",
        "badge_dot": "#223d63",
        "chip_bg": "rgba(173,185,205,0.56)",
        "section_title": "#171d28",
        "section_cta": "#5f6670",
        "item_bg": "#f3f4f6",
        "date_bg": "#d6d9de",
        "date_text": "#2c3139",
        "tail_bg": "#e4e7eb",
        "tail_text": "#2d323a",
        "error": "#a42f2f",
    },
    "connect": {
        "page_bg": "#e6eceb",
        "hero_bg": "#d8e0de",
        "hero_text": "#111823",
        "hero_sub": "#2b3a4a",
        "hero_muted": "#2b3a4a",
        "badge_bg": "rgba(255,255,255,0.5)",
        "badge_dot": "#2f7d57",
        "chip_bg": "rgba(229,235,233,0.8)",
        "section_title": "#171d28",
        "section_cta": "#2f7d57",
        "item_bg": "#f3f4f6",
        "date_bg": "#d4d7dc",
        "date_text": "#2e343c",
        "tail_bg": "#e4e7eb",
        "tail_text": "#2d323a",
        "error": "#a42f2f",
    },
}


def configure_qt_font_environment() -> None:
    if os.getenv("QT_QPA_FONTDIR"):
        return

    candidates = []
    if os.name == "nt":
        candidates.append(Path("C:/Windows/Fonts"))
    else:
        candidates.extend(
            [
                Path("/usr/share/fonts/truetype/dejavu"),
                Path("/usr/share/fonts/truetype/noto"),
                Path("/usr/share/fonts"),
            ]
        )

    for candidate in candidates:
        if candidate.exists():
            os.environ["QT_QPA_FONTDIR"] = str(candidate)
            return


def load_app_font(application: QApplication) -> str:
    global APP_FONT_FAMILY

    candidates = []
    if os.name == "nt":
        candidates.extend(
            [
                Path("C:/Windows/Fonts/segoeui.ttf"),
                Path("C:/Windows/Fonts/arial.ttf"),
            ]
        )
    else:
        candidates.extend(
            [
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                Path(
                    "/usr/share/fonts/truetype/dejavu/"
                    "DejaVuSansCondensed.ttf"
                ),
                Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
            ]
        )

    for candidate in candidates:
        if not candidate.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(candidate))
        if font_id == -1:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            APP_FONT_FAMILY = families[0]
            application.setFont(QFont(APP_FONT_FAMILY))
            return APP_FONT_FAMILY

    APP_FONT_FAMILY = DEFAULT_FONT_FAMILY
    application.setFont(QFont(APP_FONT_FAMILY))
    return APP_FONT_FAMILY


def scaled(metric: int, scale: float, floor: int = 1) -> int:
    return max(floor, int(round(metric * scale)))


def portrait_dimensions(width: int, height: int) -> tuple[int, int]:
    return min(width, height), max(width, height)


def is_windows_platform() -> bool:
    return os.name == "nt"


def window_dimensions(width: int, height: int) -> tuple[int, int]:
    safe_width = max(width, 320)
    safe_height = max(height, 240)
    if is_windows_platform():
        return safe_width, safe_height
    return portrait_dimensions(safe_width, safe_height)


def resolve_theme_name(theme_name: str, hour: int | None = None) -> str:
    normalized = theme_name.strip().lower()
    if normalized in THEMES:
        return normalized
    if hour is None:
        return "dark"
    return "dark" if hour < 7 or hour >= 19 else "light"


def display_heading(heading: str) -> str:
    mapping = {
        "In a meeting": "IN A\nMEETING",
        "Focus time": "FOCUS\nTIME",
        "Available": "AVAILABLE",
    }
    return mapping.get(heading, heading.upper())


def hero_color_key(payload: dict[str, Any]) -> str:
    current_event = payload.get("currentEvent") or {}
    if current_event.get("kind") == "focus":
        return "focus"
    if payload.get("heading") == "In a meeting":
        return "meeting"
    return "available"


def hero_icon_role(payload: dict[str, Any]) -> str:
    current_event = payload.get("currentEvent") or {}
    kind = current_event.get("kind")
    if kind in {"meeting", "focus"}:
        return kind
    return "available"


def display_range(value: str) -> str:
    return value.replace(" to ", " - ")


def hero_surface(theme: dict[str, str], color_key: str) -> str:
    return (
        "qlineargradient("
        "x1:0, y1:0, x2:1, y2:1, "
        f"stop:0 {theme[f'{color_key}_top']}, "
        f"stop:1 {theme[f'{color_key}_bottom']}"
        ")"
    )


def current_meta_text(payload: dict[str, Any]) -> str:
    current_event = payload.get("currentEvent")
    if current_event:
        return payload.get("currentTitle", "").strip()
    if payload.get("heading") == "Available":
        return "FREE NOW"
    return ""


def desired_rotation() -> str:
    return os.getenv("SCREEN_ROTATION", "right").strip().lower()


def dashboard_stylesheet(scale: float, theme: dict[str, str]) -> str:
    hero_heading = scaled(34, scale, 25)
    hero_sub = scaled(18, scale, 13)
    hero_meta = scaled(13, scale, 10)
    clock_meta = scaled(11, scale, 9)
    badge_font = scaled(10, scale, 8)
    list_title = scaled(22, scale, 16)
    list_item_title = scaled(14, scale, 11)
    list_item_body = scaled(12, scale, 10)
    chip_font = scaled(11, scale, 9)
    pill_font = scaled(9, scale, 8)
    radius = scaled(26, scale, 18)
    item_radius = scaled(18, scale, 13)
    chip_radius = scaled(13, scale, 10)
    switch_radius = scaled(16, scale, 12)
    qr_radius = scaled(18, scale, 14)
    return (
        "QWidget#root {"
        f"background-color: {theme['page_bg']};"
        f"font-family: '{APP_FONT_FAMILY}';"
        "}"
        "QScrollArea#scrollRoot {"
        "border: none;"
        "background: transparent;"
        "}"
        "QWidget#scrollContent {"
        "background: transparent;"
        "}"
        "QFrame#heroCard {"
        f"background-color: {theme['hero_bg']};"
        f"border-radius: {radius}px;"
        "}"
        "QLabel#statusBadge {"
        f"font-size: {badge_font}px;"
        "font-weight: 700;"
        "letter-spacing: 1px;"
        f"color: {theme['hero_text']};"
        f"background-color: {theme['badge_bg']};"
        f"border-radius: {chip_radius}px;"
        "padding: 7px 10px;"
        "}"
        "QFrame#badgeDot {"
        f"background-color: {theme['badge_dot']};"
        "border-radius: 6px;"
        "}"
        "QLabel#heroHeading {"
        f"font-size: {hero_heading}px;"
        "font-weight: 800;"
        f"color: {theme['hero_text']};"
        "}"
        "QLabel#heroSubheading {"
        f"font-size: {hero_sub}px;"
        f"color: {theme['hero_sub']};"
        "font-weight: 600;"
        "}"
        "QLabel#heroMeta {"
        f"font-size: {hero_meta}px;"
        "font-weight: 700;"
        f"color: {theme['hero_muted']};"
        "}"
        "QLabel#clockMeta {"
        f"font-size: {clock_meta}px;"
        f"color: {theme['hero_muted']};"
        "}"
        "QLabel#actionChip {"
        f"font-size: {chip_font}px;"
        f"background-color: {theme['chip_bg']};"
        f"color: {theme['hero_text']};"
        f"border-radius: {chip_radius}px;"
        "padding: 8px 11px;"
        "}"
        "QPushButton#primaryAction {"
        "background-color: #bc2a2a;"
        "color: #ffffff;"
        "font-weight: 700;"
        f"font-size: {hero_meta}px;"
        f"border-radius: {scaled(20, scale, 14)}px;"
        "padding: 10px;"
        "border: none;"
        "}"
        "QPushButton#iconAction {"
        f"border-radius: {scaled(20, scale, 14)}px;"
        "color: #bc2a2a;"
        "background-color: rgba(255,255,255,0.44);"
        "border: 2px solid rgba(188,42,42,0.2);"
        f"font-size: {scaled(18, scale, 14)}px;"
        "}"
        "QFrame#connectPanel {"
        "background: transparent;"
        "}"
        "QFrame#qrCard {"
        "background-color: #f9fafb;"
        f"border-radius: {qr_radius}px;"
        "}"
        "QLabel#qrCore {"
        "background-color: #1f2731;"
        f"border-radius: {scaled(14, scale, 10)}px;"
        "}"
        "QLabel#providerPill {"
        f"font-size: {pill_font}px;"
        "padding: 6px 9px;"
        f"border-radius: {scaled(10, scale, 8)}px;"
        "background-color: rgba(255,255,255,0.38);"
        "color: #4f5b64;"
        "}"
        "QLabel#providerPillConnected {"
        f"font-size: {pill_font}px;"
        "padding: 6px 9px;"
        f"border-radius: {scaled(10, scale, 8)}px;"
        "background-color: #2f7d57;"
        "color: #edfff6;"
        "}"
        "QPushButton#mobileAction {"
        "background-color: #2f7d57;"
        "color: #edfff6;"
        "font-weight: 700;"
        f"font-size: {chip_font}px;"
        f"border-radius: {scaled(20, scale, 14)}px;"
        "padding: 10px;"
        "border: none;"
        "}"
        "QFrame#listSection {"
        "background: transparent;"
        "}"
        "QLabel#listTitle {"
        f"font-size: {list_title}px;"
        "font-weight: 700;"
        f"color: {theme['section_title']};"
        "}"
        "QPushButton#listCta {"
        "background: transparent;"
        "border: none;"
        f"color: {theme['section_cta']};"
        f"font-size: {chip_font}px;"
        "font-weight: 700;"
        "}"
        "QFrame#eventCard {"
        f"background-color: {theme['item_bg']};"
        f"border-radius: {item_radius}px;"
        "}"
        "QFrame#datePill {"
        f"background-color: {theme['date_bg']};"
        f"border-radius: {scaled(13, scale, 10)}px;"
        "}"
        "QLabel#dateMonth {"
        f"font-size: {pill_font}px;"
        "font-weight: 700;"
        f"color: {theme['date_text']};"
        "}"
        "QLabel#dateDay {"
        f"font-size: {scaled(22, scale, 16)}px;"
        "font-weight: 700;"
        f"color: {theme['date_text']};"
        "}"
        "QLabel#eventTitle {"
        f"font-size: {list_item_title}px;"
        "font-weight: 700;"
        f"color: {theme['section_title']};"
        "}"
        "QLabel#eventRange, QLabel#eventSubtitle {"
        f"font-size: {list_item_body}px;"
        "color: #57616b;"
        "}"
        "QFrame#eventTail {"
        f"background-color: {theme['tail_bg']};"
        f"border-radius: {scaled(16, scale, 11)}px;"
        "}"
        "QLabel#eventTailText {"
        f"color: {theme['tail_text']};"
        f"font-size: {scaled(18, scale, 13)}px;"
        "font-weight: 600;"
        "}"
        "QFrame#statusSwitch {"
        "background: transparent;"
        "}"
        "QFrame#switchCard {"
        "background-color: #f2f3f5;"
        f"border-radius: {switch_radius}px;"
        "}"
        "QLabel#switchIcon {"
        f"font-size: {scaled(20, scale, 14)}px;"
        "}"
        "QLabel#switchTitle {"
        f"font-size: {chip_font}px;"
        "font-weight: 700;"
        "color: #1f2834;"
        "}"
        "QLabel#switchSubtitle {"
        f"font-size: {pill_font}px;"
        "color: #57616b;"
        "}"
        "QLabel#errorBar {"
        f"font-size: {pill_font}px;"
        f"color: {theme['error']};"
        "}"
    )


class DragScrollArea(QScrollArea):
    def __init__(self) -> None:
        super().__init__()
        self._dragging = False
        self._last_y = 0
        self.setObjectName("scrollRoot")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._last_y = int(event.position().y())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: ANN001
        if self._dragging:
            current_y = int(event.position().y())
            delta = current_y - self._last_y
            bar = self.verticalScrollBar()
            bar.setValue(bar.value() - delta)
            self._last_y = current_y
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
        self._dragging = False
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        self._dragging = False
        super().leaveEvent(event)


class FetchSignals(QObject):
    finished = Signal(dict)


class FetchJob(QRunnable):
    def __init__(self, app_settings: Settings, app_providers: dict[str, Any]):
        super().__init__()
        self.app_settings = app_settings
        self.app_providers = app_providers
        self.signals = FetchSignals()

    def run(self) -> None:
        payload = build_status_payload(self.app_settings, self.app_providers)
        self.signals.finished.emit(payload)


class IconWidget(QWidget):
    def __init__(self, role: str, variant: str) -> None:
        super().__init__()
        self.role = role
        self.variant = variant
        self.theme = THEMES["dark"]
        self.ui_scale = 1.0
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )

    def set_role(self, role: str) -> None:
        self.role = role
        self.update()

    def set_scale(self, scale: float) -> None:
        self.ui_scale = scale
        self.update()

    def apply_theme(self, theme: dict[str, str]) -> None:
        self.theme = theme
        self.update()

    def _icon_color(self) -> QColor:
        key = "hero_icon" if self.variant == "hero" else "next_icon"
        return QColor(self.theme[key])

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self._icon_color()
        if self.role == "meeting":
            self._draw_meeting_icon(painter, color)
            return
        if self.role == "focus":
            self._draw_focus_icon(painter, color)
            return
        if self.role == "calendar":
            self._draw_calendar_icon(painter, color)
            return
        self._draw_available_icon(painter, color)

    def _draw_meeting_icon(self, painter: QPainter, color: QColor) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        rect = QRectF(self.rect())
        body = QRectF(
            rect.width() * 0.05,
            rect.height() * 0.24,
            rect.width() * 0.58,
            rect.height() * 0.52,
        )
        radius = min(body.width(), body.height()) * 0.14
        painter.drawRoundedRect(body, radius, radius)
        lens = QPolygonF(
            [
                body.topRight() + self._point(0, body.height() * 0.17),
                self._point(rect.width() * 0.92, rect.height() * 0.26),
                self._point(rect.width() * 0.92, rect.height() * 0.74),
                body.bottomRight() - self._point(0, body.height() * 0.17),
            ]
        )
        painter.drawPolygon(lens)

    def _draw_focus_icon(self, painter: QPainter, color: QColor) -> None:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(color, max(2, scaled(5, self.ui_scale, 2)))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        rect = QRectF(self.rect())
        outer = rect.adjusted(
            rect.width() * 0.18,
            rect.height() * 0.18,
            -rect.width() * 0.18,
            -rect.height() * 0.18,
        )
        inner = rect.adjusted(
            rect.width() * 0.34,
            rect.height() * 0.34,
            -rect.width() * 0.34,
            -rect.height() * 0.34,
        )
        painter.drawEllipse(outer)
        painter.drawEllipse(inner)
        center = rect.center()
        painter.drawLine(
            self._point(center.x(), outer.top()),
            self._point(center.x(), rect.height() * 0.10),
        )
        painter.drawLine(
            self._point(center.x(), outer.bottom()),
            self._point(center.x(), rect.height() * 0.90),
        )
        painter.drawLine(
            self._point(outer.left(), center.y()),
            self._point(rect.width() * 0.10, center.y()),
        )
        painter.drawLine(
            self._point(outer.right(), center.y()),
            self._point(rect.width() * 0.90, center.y()),
        )

    def _draw_calendar_icon(self, painter: QPainter, color: QColor) -> None:
        pen = QPen(color, max(2, scaled(5, self.ui_scale, 2)))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        rect = QRectF(self.rect())
        body = rect.adjusted(
            rect.width() * 0.16,
            rect.height() * 0.18,
            -rect.width() * 0.16,
            -rect.height() * 0.14,
        )
        radius = min(body.width(), body.height()) * 0.08
        painter.drawRoundedRect(body, radius, radius)
        painter.drawLine(
            self._point(body.left(), body.top() + body.height() * 0.28),
            self._point(body.right(), body.top() + body.height() * 0.28),
        )
        painter.drawLine(
            self._point(
                body.left() + body.width() * 0.22,
                body.top() - body.height() * 0.08,
            ),
            self._point(
                body.left() + body.width() * 0.22,
                body.top() + body.height() * 0.10,
            ),
        )
        painter.drawLine(
            self._point(
                body.right() - body.width() * 0.22,
                body.top() - body.height() * 0.08,
            ),
            self._point(
                body.right() - body.width() * 0.22,
                body.top() + body.height() * 0.10,
            ),
        )
        painter.fillRect(
            QRectF(
                body.left() + body.width() * 0.18,
                body.top() + body.height() * 0.46,
                body.width() * 0.18,
                body.height() * 0.18,
            ),
            color,
        )
        painter.fillRect(
            QRectF(
                body.left() + body.width() * 0.48,
                body.top() + body.height() * 0.58,
                body.width() * 0.18,
                body.height() * 0.18,
            ),
            color,
        )

    def _draw_available_icon(self, painter: QPainter, color: QColor) -> None:
        pen = QPen(color, max(2, scaled(5, self.ui_scale, 2)))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        rect = QRectF(self.rect())
        circle = rect.adjusted(
            rect.width() * 0.20,
            rect.height() * 0.20,
            -rect.width() * 0.20,
            -rect.height() * 0.20,
        )
        painter.drawEllipse(circle)
        points = QPolygonF(
            [
                self._point(rect.width() * 0.34, rect.height() * 0.53),
                self._point(rect.width() * 0.47, rect.height() * 0.66),
                self._point(rect.width() * 0.70, rect.height() * 0.38),
            ]
        )
        painter.drawPolyline(points)

    @staticmethod
    def _point(x_pos: float, y_pos: float):
        from PySide6.QtCore import QPointF

        return QPointF(x_pos, y_pos)


class DashboardWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.thread_pool = QThreadPool.globalInstance()
        self.refresh_in_flight = False
        self.base_width, self.base_height = window_dimensions(
            settings.screen_width,
            settings.screen_height,
        )
        self.ui_scale = 1.0
        self.theme_mode = settings.ui_theme
        self.active_theme_name = resolve_theme_name(self.theme_mode)
        self.status_name = "available"
        self.theme = STATUS_PALETTES[self.status_name]

        self.setWindowTitle(settings.ui_label)
        self.setObjectName("root")
        self.root_layout = QVBoxLayout(self)

        self.scroll_root = DragScrollArea()
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("scrollContent")
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_root.setWidget(self.scroll_content)
        self.root_layout.addWidget(self.scroll_root)

        self.hero_card = QFrame()
        self.hero_card.setObjectName("heroCard")
        self.hero_layout = QVBoxLayout(self.hero_card)

        self.badge_row = QHBoxLayout()
        self.badge_dot = QFrame()
        self.badge_dot.setObjectName("badgeDot")
        self.badge_dot.setFixedSize(12, 12)
        self.badge_label = QLabel("CURRENT STATE")
        self.badge_label.setObjectName("statusBadge")
        self.badge_row.addWidget(
            self.badge_dot,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        self.badge_row.addWidget(
            self.badge_label,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        self.badge_row.addStretch(1)
        self.hero_layout.addLayout(self.badge_row)

        self.status_heading = QLabel("Available")
        self.status_heading.setObjectName("heroHeading")
        self.status_heading.setWordWrap(True)
        self.hero_layout.addWidget(self.status_heading)

        self.status_subheading = QLabel("Rest of day")
        self.status_subheading.setObjectName("heroSubheading")
        self.hero_layout.addWidget(self.status_subheading)

        self.status_meta = QLabel(settings.ui_sublabel)
        self.status_meta.setObjectName("heroMeta")
        self.hero_layout.addWidget(self.status_meta)

        self.clock_meta = QLabel("--:--")
        self.clock_meta.setObjectName("clockMeta")
        self.hero_layout.addWidget(self.clock_meta)

        self.action_row = QHBoxLayout()
        self.action_chip_a = QLabel("Open Door")
        self.action_chip_a.setObjectName("actionChip")
        self.action_chip_b = QLabel("Quick Questions OK")
        self.action_chip_b.setObjectName("actionChip")
        self.action_row.addWidget(self.action_chip_a)
        self.action_row.addWidget(self.action_chip_b)
        self.action_row.addStretch(1)
        self.hero_layout.addLayout(self.action_row)

        self.hero_footer = QHBoxLayout()
        self.primary_action = QPushButton("End Early")
        self.primary_action.setObjectName("primaryAction")
        self.primary_action.setEnabled(False)
        self.icon_action = QPushButton("✎")
        self.icon_action.setObjectName("iconAction")
        self.icon_action.setEnabled(False)
        self.hero_footer.addWidget(self.primary_action, 1)
        self.hero_footer.addWidget(self.icon_action)
        self.hero_layout.addLayout(self.hero_footer)

        self.connect_panel = QFrame()
        self.connect_panel.setObjectName("connectPanel")
        self.connect_layout = QVBoxLayout(self.connect_panel)
        self.connect_copy = QLabel(
            "Scan the QR code to sync your calendars and set your "
            "sanctuary status."
        )
        self.connect_copy.setObjectName("heroSubheading")
        self.connect_copy.setWordWrap(True)
        self.connect_copy.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connect_layout.addWidget(self.connect_copy)

        self.qr_card = QFrame()
        self.qr_card.setObjectName("qrCard")
        self.qr_layout = QVBoxLayout(self.qr_card)
        self.qr_core = QLabel("")
        self.qr_core.setObjectName("qrCore")
        self.qr_core.setFixedSize(124, 124)
        self.qr_layout.addWidget(self.qr_core, 0, Qt.AlignmentFlag.AlignCenter)
        self.connect_layout.addWidget(self.qr_card)

        self.provider_row = QHBoxLayout()
        self.provider_row.setSpacing(6)
        self.connect_layout.addLayout(self.provider_row)

        self.mobile_action = QPushButton("Open Mobile App")
        self.mobile_action.setObjectName("mobileAction")
        self.mobile_action.setEnabled(False)
        self.connect_layout.addWidget(self.mobile_action)

        self.help_label = QLabel("Need help?")
        self.help_label.setObjectName("clockMeta")
        self.help_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connect_layout.addWidget(self.help_label)

        self.hero_layout.addWidget(self.connect_panel)

        self.list_section = QFrame()
        self.list_section.setObjectName("listSection")
        self.list_layout = QVBoxLayout(self.list_section)
        self.list_header = QHBoxLayout()
        self.list_title = QLabel("Upcoming Events")
        self.list_title.setObjectName("listTitle")
        self.list_cta = QPushButton("View Calendar")
        self.list_cta.setObjectName("listCta")
        self.list_cta.setEnabled(False)
        self.list_header.addWidget(self.list_title)
        self.list_header.addStretch(1)
        self.list_header.addWidget(self.list_cta)
        self.list_layout.addLayout(self.list_header)

        self.events_container = QVBoxLayout()
        self.list_layout.addLayout(self.events_container)

        self.status_switch = QFrame()
        self.status_switch.setObjectName("statusSwitch")
        self.switch_layout = QHBoxLayout(self.status_switch)
        self.switch_layout.addWidget(
            self._build_switch_card("⚡", "Available", "Open to chat")
        )
        self.switch_layout.addWidget(
            self._build_switch_card("☾", "Focus Time", "Deep work mode")
        )

        self.error_bar = QLabel("")
        self.error_bar.setObjectName("errorBar")

        self.scroll_layout.addWidget(self.hero_card)
        self.scroll_layout.addWidget(self.list_section)
        self.scroll_layout.addWidget(self.status_switch)
        self.scroll_layout.addWidget(self.error_bar)
        self.scroll_layout.addStretch(1)

        self.apply_metrics(self.base_width, self.base_height)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(settings.refresh_seconds * 1000)
        self.refresh_timer.timeout.connect(self.refresh_payload)
        self.refresh_timer.start()

    def apply_theme(self, theme_name: str) -> None:
        self.active_theme_name = theme_name
        self.apply_metrics(max(self.width(), 1), max(self.height(), 1))

    @staticmethod
    def _clear_layout(layout: QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            if child_layout is not None:
                DashboardWindow._clear_layout(cast(QLayout, child_layout))

    def _build_switch_card(
        self,
        icon: str,
        title: str,
        subtitle: str,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("switchCard")
        layout = QVBoxLayout(card)
        icon_label = QLabel(icon)
        icon_label.setObjectName("switchIcon")
        title_label = QLabel(title)
        title_label.setObjectName("switchTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("switchSubtitle")
        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        return card

    def _status_from_payload(self, payload: dict[str, Any]) -> str:
        providers_data = payload.get("providers") or []
        if not any(item.get("connected") for item in providers_data):
            return "available"

        current_event = payload.get("currentEvent") or {}
        if current_event.get("kind") == "focus":
            return "focus"

        source_text = " ".join(
            [
                str(payload.get("heading", "")),
                str(payload.get("subheading", "")),
                str(payload.get("currentTitle", "")),
                str(payload.get("currentSubtitle", "")),
            ]
        ).lower()
        out_tokens = ["out of office", "ooo", "vacation", "pto", "away"]
        if any(token in source_text for token in out_tokens):
            return "ooo"

        if payload.get("currentEvent"):
            return "busy"
        return "available"

    def _apply_status_preset(self, payload: dict[str, Any]) -> None:
        status = self._status_from_payload(payload)
        self.status_name = status
        self.theme = STATUS_PALETTES[status]

        presets = {
            "available": {
                "badge": "CURRENT STATE",
                "heading": "Available",
                "sub": payload.get("currentRange", "Rest of day"),
                "chip_a": "Open Door",
                "chip_b": "Quick Questions OK",
                "list_title": "Upcoming Events",
                "list_cta": "View Calendar",
                "show_footer": False,
                "show_connect": False,
                "show_list": True,
                "show_switch": False,
            },
            "busy": {
                "badge": "CURRENTLY ACTIVE",
                "heading": "Busy",
                "sub": payload.get("subheading", "In progress"),
                "chip_a": "Do Not Disturb",
                "chip_b": "Urgent Only",
                "list_title": "Upcoming Next",
                "list_cta": "View Calendar",
                "show_footer": True,
                "show_connect": False,
                "show_list": True,
                "show_switch": False,
            },
            "focus": {
                "badge": "CURRENT STATE",
                "heading": "Focusing",
                "sub": "Deep work mode",
                "chip_a": "Extremely Silent",
                "chip_b": "Messaging Only",
                "list_title": "Coming Up",
                "list_cta": "Next 24 hours",
                "show_footer": False,
                "show_connect": False,
                "show_list": True,
                "show_switch": False,
            },
            "ooo": {
                "badge": "CURRENT STATE",
                "heading": "Out of Office",
                "sub": payload.get("subheading", "Back soon"),
                "chip_a": "Away from Desk",
                "chip_b": "Email for response",
                "list_title": "Update Status",
                "list_cta": "",
                "show_footer": False,
                "show_connect": False,
                "show_list": False,
                "show_switch": True,
            },
            "connect": {
                "badge": "SETUP",
                "heading": "Connect Your World",
                "sub": "Scan the QR code to sync your calendars and set your "
                "sanctuary status.",
                "chip_a": "",
                "chip_b": "",
                "list_title": "Providers",
                "list_cta": "",
                "show_footer": False,
                "show_connect": True,
                "show_list": False,
                "show_switch": False,
            },
        }
        preset = presets[status]
        self.badge_label.setText(preset["badge"])
        self.status_heading.setText(preset["heading"])
        self.status_subheading.setText(preset["sub"])
        self.action_chip_a.setText(preset["chip_a"])
        self.action_chip_b.setText(preset["chip_b"])
        self.action_chip_a.setVisible(bool(preset["chip_a"]))
        self.action_chip_b.setVisible(bool(preset["chip_b"]))
        self.list_title.setText(preset["list_title"])
        self.list_cta.setText(preset["list_cta"])
        self.list_cta.setVisible(bool(preset["list_cta"]))
        self.primary_action.setVisible(preset["show_footer"])
        self.icon_action.setVisible(preset["show_footer"])
        self.connect_panel.setVisible(preset["show_connect"])
        self.list_section.setVisible(preset["show_list"])
        self.status_switch.setVisible(preset["show_switch"])

    def _render_provider_pills(
        self,
        providers_data: list[dict[str, Any]],
    ) -> None:
        self._clear_layout(self.provider_row)
        if not providers_data:
            empty = QLabel("No providers configured")
            empty.setObjectName("providerPill")
            self.provider_row.addWidget(empty)
            self.provider_row.addStretch(1)
            return
        for provider in providers_data:
            pill = QLabel(provider.get("displayName", "Provider"))
            if provider.get("connected"):
                pill.setObjectName("providerPillConnected")
            else:
                pill.setObjectName("providerPill")
            self.provider_row.addWidget(pill)
        self.provider_row.addStretch(1)

    def _build_event_card(
        self,
        month: str,
        day: str,
        title: str,
        event_range: str,
        subtitle: str,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("eventCard")
        layout = QHBoxLayout(card)

        date_pill = QFrame()
        date_pill.setObjectName("datePill")
        date_layout = QVBoxLayout(date_pill)
        month_label = QLabel(month)
        month_label.setObjectName("dateMonth")
        month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        day_label = QLabel(day)
        day_label.setObjectName("dateDay")
        day_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_layout.addWidget(month_label)
        date_layout.addWidget(day_label)

        copy_layout = QVBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("eventTitle")
        range_label = QLabel(event_range)
        range_label.setObjectName("eventRange")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("eventSubtitle")
        copy_layout.addWidget(title_label)
        copy_layout.addWidget(range_label)
        copy_layout.addWidget(subtitle_label)

        tail = QFrame()
        tail.setObjectName("eventTail")
        tail.setFixedSize(34, 34)
        tail_layout = QVBoxLayout(tail)
        tail_text = QLabel("›")
        tail_text.setObjectName("eventTailText")
        tail_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tail_layout.addWidget(tail_text)

        layout.addWidget(date_pill)
        layout.addLayout(copy_layout, 1)
        layout.addWidget(tail)
        return card

    def _render_upcoming(self, payload: dict[str, Any]) -> None:
        self._clear_layout(self.events_container)
        upcoming = payload.get("upcoming") or []
        if not upcoming:
            empty = QLabel(
                "No upcoming events in the current lookahead window."
            )
            empty.setObjectName("eventSubtitle")
            self.events_container.addWidget(empty)
            return

        generated_at = payload.get("generatedAt")
        try:
            if generated_at:
                base = datetime.fromisoformat(generated_at)
            else:
                base = datetime.now()
        except ValueError:
            base = datetime.now()

        start_day = base.replace(hour=0, minute=0, second=0, microsecond=0)
        for index, event in enumerate(upcoming[:4]):
            event_day = start_day + timedelta(days=index)
            month = event_day.strftime("%b").upper()
            day = str(event_day.day)
            card = self._build_event_card(
                month,
                day,
                event.get("title", "Untitled"),
                display_range(event.get("range", "")),
                event.get("subtitle", ""),
            )
            self.events_container.addWidget(card)

    def apply_metrics(self, width: int, height: int) -> None:
        scale = min(width / 320, height / 480)
        self.ui_scale = max(0.74, min(scale * 0.92, 1.1))
        self.setStyleSheet(dashboard_stylesheet(self.ui_scale, self.theme))

        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        self.scroll_layout.setContentsMargins(
            8,
            8,
            8,
            8
        )
        self.scroll_layout.setSpacing(scaled(12, self.ui_scale, 9))

        self.hero_layout.setContentsMargins(
            scaled(18, self.ui_scale, 13),
            scaled(18, self.ui_scale, 13),
            scaled(18, self.ui_scale, 13),
            scaled(16, self.ui_scale, 11),
        )
        self.hero_layout.setSpacing(scaled(8, self.ui_scale, 5))

        self.qr_core.setFixedSize(
            scaled(124, self.ui_scale, 92),
            scaled(124, self.ui_scale, 92),
        )
        self.primary_action.setMinimumHeight(scaled(40, self.ui_scale, 30))
        self.icon_action.setFixedSize(
            scaled(48, self.ui_scale, 36),
            scaled(40, self.ui_scale, 30),
        )
        self.mobile_action.setMinimumHeight(scaled(40, self.ui_scale, 30))

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self.apply_metrics(max(self.width(), 1), max(self.height(), 1))

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        QTimer.singleShot(0, self.refresh_payload)

    def refresh_payload(self) -> None:
        if self.refresh_in_flight:
            return
        self.refresh_in_flight = True
        job = FetchJob(settings, providers)
        job.signals.finished.connect(self.apply_payload)
        self.thread_pool.start(job)

    def apply_payload(self, payload: dict[str, Any]) -> None:
        self.refresh_in_flight = False
        generated_at = payload.get("generatedAt", "")
        if self.theme_mode == "auto" and generated_at:
            hour = int(generated_at[11:13])
            theme_name = resolve_theme_name("auto", hour)
            if theme_name != self.active_theme_name:
                self.apply_theme(theme_name)

        self._apply_status_preset(payload)
        subtitle = payload.get("currentSubtitle", settings.ui_sublabel)
        self.status_meta.setText(subtitle)
        clock_text = payload.get("clock", "--:--")
        date_text = payload.get("dateLabel", "")
        self.clock_meta.setText(f"{clock_text} • {date_text}")
        self.error_bar.setText(" | ".join(payload.get("errors") or []))
        self._render_provider_pills(payload.get("providers") or [])
        self._render_upcoming(payload)
        self.apply_metrics(max(self.width(), 1), max(self.height(), 1))


class RotatedWindow(QWidget):
    def __init__(
        self,
        content: DashboardWindow,
        rotation: str,
        window_width: int,
        window_height: int,
    ) -> None:
        super().__init__()
        self.content = content
        self.rotation = rotation
        self.content.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.content.setWindowFlag(Qt.WindowType.Tool, True)
        self.content.installEventFilter(self)
        self.content.move(-10000, -10000)
        self.content.show()
        self.setObjectName("root")
        self.setWindowTitle(content.windowTitle())
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setFixedSize(window_width, window_height)

    def eventFilter(self, watched, event) -> bool:  # noqa: ANN001
        if watched is self.content and event.type() in {
            QEvent.Type.Paint,
            QEvent.Type.Resize,
            QEvent.Type.UpdateRequest,
            QEvent.Type.LayoutRequest,
        }:
            self.update()
        return super().eventFilter(watched, event)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        pixmap = QPixmap(self.content.size())
        pixmap.fill(Qt.GlobalColor.transparent)
        self.content.render(pixmap)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self.rotation == "left":
            painter.translate(0, self.height())
            painter.rotate(-90)
        else:
            painter.translate(self.width(), 0)
            painter.rotate(90)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()


def create_application() -> QApplication:
    configure_qt_font_environment()
    existing_app = QApplication.instance()
    if existing_app is None:
        application = QApplication(sys.argv)
        application.setApplicationName(settings.ui_label)
    else:
        application = cast(QApplication, existing_app)
    load_app_font(application)
    return application


def export_preview(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target_path = output_path.with_name(f"{timestamp}-{output_path.name}")
    application = create_application()
    window = DashboardWindow()
    window_width, window_height = window_dimensions(
        settings.screen_width,
        settings.screen_height,
    )
    window.resize(window_width, window_height)
    window.apply_payload(build_status_payload(settings, providers))
    window.show()
    application.processEvents()
    pixmap = QPixmap(window.size())
    pixmap.fill(Qt.GlobalColor.transparent)
    window.render(pixmap)
    if not pixmap.save(str(target_path)):
        raise RuntimeError(f"Failed to write preview image to {target_path}")
    window.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--export-preview",
        type=Path,
        help="Render the current dashboard state to a PNG file and exit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.export_preview and "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    application = create_application()
    if args.export_preview:
        export_preview(args.export_preview)
        return 0

    window = DashboardWindow()
    window_width, window_height = window_dimensions(
        settings.screen_width,
        settings.screen_height,
    )
    if settings.fullscreen_mode and not is_windows_platform():
        window.showFullScreen()
    else:
        screen = window.screen() or application.primaryScreen()
        if screen is not None:
            available_geometry = screen.availableGeometry()
            screen_width = max(available_geometry.width(), 320)
            screen_height = max(available_geometry.height(), 240)
            rotation_needed = (
                not is_windows_platform() and screen_width > screen_height
            )
            if rotation_needed:
                window.resize(window_width, window_height)
                rotated_window = RotatedWindow(
                    window,
                    desired_rotation(),
                    screen_width,
                    screen_height,
                )
                rotated_window.move(
                    available_geometry.x(),
                    available_geometry.y(),
                )
                rotated_window.show()
                return application.exec()

            if not is_windows_platform():
                window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
                window.setFixedSize(window_width, window_height)
            else:
                window.resize(window_width, window_height)
            window.move(
                available_geometry.x()
                + max((screen_width - window_width) // 2, 0),
                available_geometry.y()
                + max((screen_height - window_height) // 2, 0),
            )
        else:
            window.resize(window_width, window_height)
        window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
