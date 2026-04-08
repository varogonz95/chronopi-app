from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Any

from dotenv import load_dotenv
from PySide6.QtCore import (
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
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .config import Settings
from .dashboard import build_status_payload
from .providers import TokenStore, build_provider_registry

load_dotenv()

settings = Settings.from_env()
token_store = TokenStore(settings.token_store_path)
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
        "available_top": "#b7c2bc",
        "available_bottom": "#97a59f",
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
        "available_top": "#d9dfda",
        "available_bottom": "#c5cec8",
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


def dashboard_stylesheet(scale: float, theme: dict[str, str]) -> str:
    hero_heading = scaled(40, scale, 26)
    hero_meta = scaled(14, scale, 10)
    hero_range = scaled(42, scale, 28)
    next_eyebrow = scaled(28, scale, 18)
    next_title = scaled(22, scale, 16)
    next_range = scaled(24, scale, 16)
    radius = scaled(26, scale, 18)
    next_radius = scaled(18, scale, 14)
    divider_radius = scaled(7, scale, 5)
    return (
        "QWidget#root {"
        f"background-color: {theme['background']};"
        f"font-family: '{APP_FONT_FAMILY}';"
        "}"
        "QLabel#heroHeading {"
        f"font-size: {hero_heading}px;"
        "font-weight: 800;"
        f"color: {theme['hero_text']};"
        "line-height: 1.0;"
        "}"
        "QLabel#heroMeta {"
        f"font-size: {hero_meta}px;"
        "font-weight: 700;"
        f"color: {theme['hero_meta']};"
        "letter-spacing: 1px;"
        "text-transform: uppercase;"
        "}"
        "QLabel#heroRange {"
        f"font-size: {hero_range}px;"
        "font-weight: 800;"
        f"color: {theme['next_text']};"
        "}"
        "QLabel#nextEyebrow {"
        f"font-size: {next_eyebrow}px;"
        "font-weight: 800;"
        f"color: {theme['next_text']};"
        "}"
        "QLabel#nextTitle {"
        f"font-size: {next_title}px;"
        f"color: {theme['next_text']};"
        "font-weight: 500;"
        "}"
        "QLabel#nextRange {"
        f"font-size: {next_range}px;"
        f"color: {theme['next_muted']};"
        "font-weight: 500;"
        "}"
        "QFrame#nextCard {"
        "background: qlineargradient("
        f"x1:0, y1:0, x2:1, y2:1, stop:0 {theme['next_top']}, "
        f"stop:1 {theme['next_bottom']});"
        f"border-radius: {next_radius}px;"
        "}"
        "QFrame#divider {"
        f"background-color: {theme['divider']};"
        f"border-radius: {divider_radius}px;"
        "}"
        "QFrame#heroCard {"
        f"border-radius: {radius}px;"
        "}"
    )


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
        self.base_width, self.base_height = portrait_dimensions(
            max(settings.screen_width, 320),
            max(settings.screen_height, 320),
        )
        self.ui_scale = 1.0
        self.theme_mode = settings.ui_theme
        self.active_theme_name = resolve_theme_name(self.theme_mode)
        self.theme = THEMES[self.active_theme_name]
        self.hero_color_name = "meeting"

        self.setWindowTitle(settings.ui_label)
        self.setObjectName("root")
        self.root_layout = QVBoxLayout(self)

        self.status_card = QFrame()
        self.status_card.setObjectName("heroCard")
        self.status_layout = QVBoxLayout(self.status_card)
        self.status_top = QHBoxLayout()
        self.status_icon = IconWidget("meeting", "hero")
        self.status_heading = QLabel("IN A\nMEETING")
        self.status_heading.setObjectName("heroHeading")
        self.status_heading.setWordWrap(True)
        self.status_heading.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.status_top.addWidget(
            self.status_icon,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        self.status_top.addWidget(self.status_heading, 1)
        self.status_layout.addLayout(self.status_top)
        self.status_meta = QLabel("")
        self.status_meta.setObjectName("heroMeta")
        self.status_meta.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.status_layout.addWidget(self.status_meta)
        self.status_layout.addStretch(1)

        self.range_label = QLabel("--")
        self.range_label.setObjectName("heroRange")
        self.range_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.range_label.setWordWrap(False)
        self.status_layout.addWidget(self.range_label)
        self.status_layout.addStretch(1)

        self.divider = QFrame()
        self.divider.setObjectName("divider")

        self.next_card = QFrame()
        self.next_card.setObjectName("nextCard")
        self.next_layout = QHBoxLayout(self.next_card)
        self.next_text_layout = QVBoxLayout()
        self.next_eyebrow = QLabel("NEXT:")
        self.next_eyebrow.setObjectName("nextEyebrow")
        self.next_title = QLabel("Loading")
        self.next_title.setObjectName("nextTitle")
        self.next_title.setWordWrap(True)
        self.next_range = QLabel("Checking your calendar")
        self.next_range.setObjectName("nextRange")
        self.next_range.setWordWrap(True)
        self.next_text_layout.addWidget(self.next_eyebrow)
        self.next_text_layout.addStretch(1)
        self.next_text_layout.addWidget(self.next_title)
        self.next_text_layout.addWidget(self.next_range)
        self.next_icon = IconWidget("calendar", "next")

        self.next_layout.addLayout(self.next_text_layout, 1)
        self.next_layout.addWidget(
            self.next_icon,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )

        self.root_layout.addWidget(self.status_card, 7)
        self.root_layout.addWidget(self.divider)
        self.root_layout.addWidget(self.next_card, 4)

        self.apply_metrics(self.base_width, self.base_height)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(settings.refresh_seconds * 1000)
        self.refresh_timer.timeout.connect(self.refresh_payload)
        self.refresh_timer.start()

    def apply_theme(self, theme_name: str) -> None:
        self.active_theme_name = theme_name
        self.theme = THEMES[theme_name]
        self.apply_metrics(max(self.width(), 1), max(self.height(), 1))

    def _apply_card_styles(self) -> None:
        radius = scaled(26, self.ui_scale, 18)
        self.status_card.setStyleSheet(
            "QFrame#heroCard {"
            f"background: {hero_surface(self.theme, self.hero_color_name)};"
            f"border-radius: {radius}px;"
            "}"
        )

    def apply_metrics(self, width: int, height: int) -> None:
        scale = min(width / 320, height / 480)
        self.ui_scale = max(0.90, min(scale, 1.24))
        self.setStyleSheet(dashboard_stylesheet(self.ui_scale, self.theme))

        self.root_layout.setContentsMargins(
            scaled(12, self.ui_scale, 8),
            scaled(14, self.ui_scale, 8),
            scaled(12, self.ui_scale, 8),
            scaled(12, self.ui_scale, 8),
        )
        self.root_layout.setSpacing(scaled(9, self.ui_scale, 6))
        self.status_layout.setContentsMargins(
            scaled(18, self.ui_scale, 14),
            scaled(18, self.ui_scale, 14),
            scaled(18, self.ui_scale, 14),
            scaled(20, self.ui_scale, 14),
        )
        self.status_layout.setSpacing(scaled(8, self.ui_scale, 6))
        self.status_top.setSpacing(scaled(10, self.ui_scale, 8))
        self.next_layout.setContentsMargins(
            scaled(16, self.ui_scale, 12),
            scaled(14, self.ui_scale, 10),
            scaled(16, self.ui_scale, 12),
            scaled(14, self.ui_scale, 10),
        )
        self.next_layout.setSpacing(scaled(10, self.ui_scale, 8))
        self.next_text_layout.setSpacing(scaled(4, self.ui_scale, 3))

        hero_icon_width = scaled(164, self.ui_scale, 96)
        hero_icon_height = scaled(106, self.ui_scale, 62)
        self.status_icon.set_scale(self.ui_scale)
        self.status_icon.apply_theme(self.theme)
        self.status_icon.setFixedSize(hero_icon_width, hero_icon_height)

        next_icon_size = scaled(82, self.ui_scale, 54)
        self.next_icon.set_scale(self.ui_scale)
        self.next_icon.apply_theme(self.theme)
        self.next_icon.setFixedSize(next_icon_size, next_icon_size)

        self.divider.setFixedHeight(scaled(10, self.ui_scale, 6))
        self._apply_card_styles()

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

        self.hero_color_name = hero_color_key(payload)
        self.status_icon.set_role(hero_icon_role(payload))
        self.status_heading.setText(display_heading(payload["heading"]))
        self.status_meta.setText(current_meta_text(payload))
        self.status_meta.setVisible(bool(self.status_meta.text()))
        self.range_label.setText(display_range(payload["currentRange"]))
        self._apply_card_styles()

        next_event = payload.get("nextEvent")
        if next_event:
            self.next_title.setText(next_event["title"])
            self.next_range.setText(display_range(next_event["range"]))
        else:
            self.next_title.setText("Nothing scheduled")
            self.next_range.setText("Calendar is clear")


def create_application() -> QApplication:
    configure_qt_font_environment()
    application = QApplication.instance()
    if application is None:
        application = QApplication(sys.argv)
        application.setApplicationName(settings.ui_label)
        load_app_font(application)
    else:
        load_app_font(application)
    return application


def export_preview(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    application = create_application()
    window = DashboardWindow()
    portrait_width, portrait_height = portrait_dimensions(
        settings.screen_width,
        settings.screen_height,
    )
    window.resize(portrait_width, portrait_height)
    window.apply_payload(build_status_payload(settings, providers))
    window.show()
    application.processEvents()
    pixmap = QPixmap(window.size())
    pixmap.fill(Qt.GlobalColor.transparent)
    window.render(pixmap)
    if not pixmap.save(str(output_path)):
        raise RuntimeError(f"Failed to write preview image to {output_path}")
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
    portrait_width, portrait_height = portrait_dimensions(
        settings.screen_width,
        settings.screen_height,
    )
    if settings.fullscreen_mode:
        window.showFullScreen()
    else:
        screen = window.screen() or application.primaryScreen()
        if screen is not None:
            available_geometry = screen.availableGeometry()
            window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
            window.setFixedSize(
                max(available_geometry.width(), 320),
                max(available_geometry.height(), 240),
            )
            window.move(available_geometry.x(), available_geometry.y())
        else:
            window.resize(portrait_width, portrait_height)
        window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
