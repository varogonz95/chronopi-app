from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Any

from dotenv import load_dotenv
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
import qrcode

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
        "background": "#081015",
        "surface": "#10181d",
        "surface_alt": "#131d23",
        "card": "#152027",
        "line": "#29404a",
        "text": "#f3ede4",
        "muted": "#c0b8ae",
        "subtle": "#8ca39a",
        "meeting": "#e88762",
        "focus": "#d0aa5a",
        "available": "#70bda3",
        "button_bg": "#1a2830",
        "button_text": "#f3ede4",
        "button_border": "#3a5661",
        "qr_bg": "#fffaf1",
        "qr_fg": "#081015",
    },
    "light": {
        "background": "#f4efe7",
        "surface": "#fffaf3",
        "surface_alt": "#f7f1e7",
        "card": "#fffdf8",
        "line": "#c7d0ce",
        "text": "#182329",
        "muted": "#526069",
        "subtle": "#617b73",
        "meeting": "#d86f46",
        "focus": "#b4882f",
        "available": "#2d8a71",
        "button_bg": "#edf2f0",
        "button_text": "#182329",
        "button_border": "#b8c5c0",
        "qr_bg": "#ffffff",
        "qr_fg": "#182329",
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


def dashboard_stylesheet(scale: float, theme: dict[str, str]) -> str:
    eyebrow = scaled(12, scale, 10)
    clock = scaled(50, scale, 32)
    body = scaled(16, scale, 12)
    heading = scaled(28, scale, 20)
    title = scaled(23, scale, 16)
    section = scaled(13, scale, 10)
    footer = scaled(12, scale, 10)
    card_title = scaled(18, scale, 13)
    card_body = scaled(14, scale, 11)
    return (
        "QWidget#root {"
        f"background-color: {theme['background']};"
        f"color: {theme['text']};"
        f"font-family: '{APP_FONT_FAMILY}';"
        "}"
        "QLabel#eyebrow {"
        f"color: {theme['subtle']};"
        f"font-size: {eyebrow}px;"
        "font-weight: 700;"
        "letter-spacing: 1px;"
        "text-transform: uppercase;"
        "}"
        "QLabel#clock {"
        f"font-size: {clock}px;"
        "font-weight: 700;"
        f"color: {theme['text']};"
        "}"
        "QLabel#dateLabel {"
        f"font-size: {body}px;"
        f"color: {theme['muted']};"
        "}"
        "QLabel#heading {"
        f"font-size: {heading}px;"
        "font-weight: 700;"
        f"color: {theme['text']};"
        "}"
        "QLabel#subheading {"
        f"font-size: {body}px;"
        f"color: {theme['muted']};"
        "}"
        "QLabel#currentTitle {"
        f"font-size: {title}px;"
        "font-weight: 700;"
        f"color: {theme['text']};"
        "}"
        "QLabel#currentSubtitle {"
        f"font-size: {body}px;"
        f"color: {theme['muted']};"
        "}"
        "QLabel#sectionTitle {"
        f"font-size: {section}px;"
        "font-weight: 700;"
        f"color: {theme['subtle']};"
        "letter-spacing: 1px;"
        "}"
        "QLabel#footer {"
        f"font-size: {footer}px;"
        f"color: {theme['muted']};"
        "}"
        "QLabel#eventTitle {"
        f"font-size: {card_title}px;"
        "font-weight: 700;"
        f"color: {theme['text']};"
        "}"
        "QLabel#eventSubtitle {"
        f"font-size: {card_body}px;"
        f"color: {theme['muted']};"
        "}"
        "QLabel#eventTime {"
        f"font-size: {card_body}px;"
        f"color: {theme['text']};"
        "}"
        "QLabel#setupTitle {"
        f"font-size: {card_title}px;"
        "font-weight: 700;"
        f"color: {theme['text']};"
        "}"
        "QLabel#setupHint {"
        f"font-size: {card_body}px;"
        f"color: {theme['muted']};"
        "}"
        "QLabel#setupUrl {"
        f"font-size: {card_body}px;"
        f"color: {theme['available']};"
        "text-decoration: none;"
        "}"
        "QPushButton#themeToggle {"
        f"background-color: {theme['button_bg']};"
        f"color: {theme['button_text']};"
        f"border: 1px solid {theme['button_border']};"
        f"border-radius: {scaled(16, scale, 12)}px;"
        f"padding: {scaled(7, scale, 5)}px {scaled(12, scale, 9)}px;"
        f"font-size: {footer}px;"
        "font-weight: 700;"
        "}"
        "QPushButton#themeToggle:pressed {"
        f"background-color: {theme['surface_alt']};"
        "}"
    )


def accent_color(payload: dict[str, Any]) -> str:
    current_event = payload.get("currentEvent") or {}
    if current_event.get("kind") == "focus":
        return "#d7a44b"
    if payload.get("heading") == "In a meeting":
        return "#e17d5c"
    return "#6fc0a8"


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


class RingWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.remaining_minutes = 0
        self.ring_label = "clear"
        self.progress = 1.0
        self.accent = QColor(THEMES["dark"]["available"])
        self.track = QColor(THEMES["dark"]["line"])
        self.text_color = QColor(THEMES["dark"]["text"])
        self.subtext_color = QColor(THEMES["dark"]["muted"])
        self.ui_scale = 1.0
        self.setMinimumSize(220, 220)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

    def set_scale(self, scale: float) -> None:
        self.ui_scale = scale
        min_size = scaled(170, scale, 150)
        self.setMinimumSize(min_size, min_size)
        self.update()

    def set_state(
        self,
        remaining_minutes: int,
        ring_label: str,
        progress: float,
        accent: str,
    ) -> None:
        self.remaining_minutes = remaining_minutes
        self.ring_label = ring_label
        self.progress = progress
        self.accent = QColor(accent)
        self.update()

    def apply_theme(self, theme: dict[str, str]) -> None:
        self.track = QColor(theme["line"])
        self.text_color = QColor(theme["text"])
        self.subtext_color = QColor(theme["muted"])
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        inset = scaled(16, self.ui_scale, 12)
        bounds = self.rect().adjusted(inset, inset, -inset, -inset)
        size = min(bounds.width(), bounds.height())
        x_pos = bounds.center().x() - (size / 2)
        y_pos = bounds.center().y() - (size / 2)
        ring_rect = bounds.adjusted(
            int(x_pos - bounds.x()),
            int(y_pos - bounds.y()),
            int((x_pos + size) - bounds.right() - 1),
            int((y_pos + size) - bounds.bottom() - 1),
        )

        stroke_width = scaled(14, self.ui_scale, 10)
        track_pen = QPen(self.track, stroke_width)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(ring_rect, 90 * 16, -360 * 16)

        active_pen = QPen(self.accent, stroke_width)
        active_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(active_pen)
        painter.drawArc(ring_rect, 90 * 16, int(-360 * 16 * self.progress))

        painter.setPen(self.text_color)
        minutes_font = QFont(
            APP_FONT_FAMILY,
            scaled(30, self.ui_scale, 22),
            QFont.Weight.Bold,
        )
        painter.setFont(minutes_font)
        value_rect = ring_rect.adjusted(
            0,
            -scaled(10, self.ui_scale, 8),
            0,
            -scaled(14, self.ui_scale, 10),
        )
        painter.drawText(
            value_rect,
            Qt.AlignmentFlag.AlignCenter,
            str(self.remaining_minutes),
        )

        label_font = QFont(
            APP_FONT_FAMILY,
            scaled(10, self.ui_scale, 9),
        )
        painter.setFont(label_font)
        painter.setPen(self.subtext_color)
        label_rect = ring_rect.adjusted(
            0,
            scaled(82, self.ui_scale, 56),
            0,
            0,
        )
        painter.drawText(
            label_rect,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            self.ring_label,
        )


class UpcomingCard(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("upcomingCard")
        self.ui_scale = 1.0
        self.kind = "meeting"
        self.theme = THEMES["dark"]
        self.title_label = QLabel("No upcoming events")
        self.title_label.setObjectName("eventTitle")
        self.subtitle_label = QLabel("")
        self.subtitle_label.setObjectName("eventSubtitle")
        self.time_label = QLabel("")
        self.time_label.setObjectName("eventTime")

        self.card_layout = QVBoxLayout(self)
        self.card_layout.addWidget(self.title_label)
        self.card_layout.addWidget(self.subtitle_label)
        self.card_layout.addWidget(self.time_label)
        self.apply_scale(1.0)
        self.set_kind_style("meeting")

    def apply_scale(self, scale: float) -> None:
        self.ui_scale = scale
        self.card_layout.setContentsMargins(
            scaled(16, scale, 12),
            scaled(14, scale, 10),
            scaled(16, scale, 12),
            scaled(14, scale, 10),
        )
        self.card_layout.setSpacing(scaled(5, scale, 4))
        self.set_kind_style(self.kind)

    def apply_theme(self, theme: dict[str, str]) -> None:
        self.theme = theme
        self.set_kind_style(self.kind)

    def set_kind_style(self, kind: str) -> None:
        self.kind = kind
        border = (
            self.theme["focus"]
            if kind == "focus"
            else self.theme["available"]
        )
        self.setStyleSheet(
            "QFrame#upcomingCard {"
            f"background-color: {self.theme['card']};"
            f"border: 1px solid {border};"
            f"border-radius: {scaled(16, self.ui_scale, 12)}px;"
            "}"
        )

    def set_event(self, event: dict[str, Any] | None) -> None:
        if not event:
            self.title_label.setText("No more events")
            self.subtitle_label.setText("Calendar is clear")
            self.time_label.setText("")
            self.set_kind_style("meeting")
            return
        self.title_label.setText(event["title"])
        self.subtitle_label.setText(event["subtitle"])
        self.time_label.setText(event["range"])
        self.set_kind_style(event["kind"])


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
        self.compact_mode = False
        self.visible_upcoming_limit = 4
        self.theme_mode = settings.ui_theme
        self.active_theme_name = resolve_theme_name(self.theme_mode)
        self.theme = THEMES[self.active_theme_name]

        self.setWindowTitle(settings.ui_label)
        self.setObjectName("root")
        self.root_layout = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        self.header_layout = header_layout
        header_text = QVBoxLayout()
        self.header_text_layout = header_text
        self.brand_label = QLabel(settings.ui_label)
        self.brand_label.setObjectName("eyebrow")
        self.brand_sublabel = QLabel(settings.ui_sublabel)
        self.brand_sublabel.setObjectName("dateLabel")
        header_text.addWidget(self.brand_label)
        header_text.addWidget(self.brand_sublabel)
        header_text.addStretch(1)

        clock_layout = QVBoxLayout()
        self.clock_layout = clock_layout
        self.clock_right = QVBoxLayout()
        self.clock_right.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.theme_button = QPushButton("")
        self.theme_button.setObjectName("themeToggle")
        self.theme_button.clicked.connect(self.toggle_theme)
        self.clock_label = QLabel("--:--")
        self.clock_label.setObjectName("clock")
        self.clock_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.date_label = QLabel("")
        self.date_label.setObjectName("dateLabel")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.clock_right.addWidget(
            self.theme_button,
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        self.clock_right.addWidget(self.clock_label)
        self.clock_right.addWidget(self.date_label)

        header_layout.addLayout(header_text, 1)
        header_layout.addLayout(self.clock_right)

        hero_frame = QFrame()
        hero_frame.setObjectName("heroFrame")
        self.hero_frame = hero_frame
        self.hero_layout = QBoxLayout(
            QBoxLayout.Direction.LeftToRight,
            hero_frame,
        )

        self.ring_widget = RingWidget()

        text_layout = QVBoxLayout()
        self.text_layout = text_layout
        self.heading_label = QLabel("Loading")
        self.heading_label.setObjectName("heading")
        self.subheading_label = QLabel("Checking connected providers")
        self.subheading_label.setObjectName("subheading")
        self.current_title_label = QLabel("Chronopi")
        self.current_title_label.setObjectName("currentTitle")
        self.current_subtitle_label = QLabel("")
        self.current_subtitle_label.setObjectName("currentSubtitle")
        self.next_event_label = QLabel("")
        self.next_event_label.setObjectName("footer")
        self.next_event_label.setWordWrap(True)
        text_layout.addWidget(self.heading_label)
        text_layout.addWidget(self.subheading_label)
        text_layout.addSpacing(8)
        text_layout.addWidget(self.current_title_label)
        text_layout.addWidget(self.current_subtitle_label)
        text_layout.addSpacing(12)
        text_layout.addWidget(self.next_event_label)
        text_layout.addStretch(1)

        self.hero_layout.addWidget(self.ring_widget, 1)
        self.hero_layout.addLayout(text_layout, 2)

        upcoming_title = QLabel("Upcoming")
        upcoming_title.setObjectName("sectionTitle")
        self.upcoming_title = upcoming_title
        self.root_layout.addLayout(header_layout)
        self.root_layout.addWidget(hero_frame)
        self.root_layout.addWidget(upcoming_title)

        self.upcoming_cards: list[UpcomingCard] = []
        self.upcoming_layout = QVBoxLayout()
        for _ in range(4):
            card = UpcomingCard()
            self.upcoming_cards.append(card)
            self.upcoming_layout.addWidget(card)
        self.root_layout.addLayout(self.upcoming_layout)

        self.setup_card = QFrame()
        self.setup_card.setObjectName("setupCard")
        self.setup_layout = QHBoxLayout(self.setup_card)
        self.setup_qr = QLabel()
        self.setup_qr.setScaledContents(True)
        self.setup_qr.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self.setup_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setup_text_layout = QVBoxLayout()
        self.setup_title = QLabel("Connect Calendars")
        self.setup_title.setObjectName("setupTitle")
        self.setup_hint = QLabel(
            "Scan from your phone to open the provider setup page."
        )
        self.setup_hint.setObjectName("setupHint")
        self.setup_hint.setWordWrap(True)
        self.setup_url = QLabel()
        self.setup_url.setObjectName("setupUrl")
        self.setup_url.setTextFormat(Qt.TextFormat.RichText)
        self.setup_url.setOpenExternalLinks(True)
        self.setup_url.setWordWrap(True)
        self.setup_text_layout.addWidget(self.setup_title)
        self.setup_text_layout.addWidget(self.setup_hint)
        self.setup_text_layout.addWidget(self.setup_url)
        self.setup_text_layout.addStretch(1)
        self.setup_layout.addWidget(self.setup_qr)
        self.setup_layout.addLayout(self.setup_text_layout, 1)
        self.root_layout.addWidget(self.setup_card)

        self.status_label = QLabel("Providers: checking")
        self.status_label.setObjectName("footer")
        self.status_label.setWordWrap(True)
        self.error_label = QLabel("")
        self.error_label.setObjectName("footer")
        self.error_label.setWordWrap(True)
        self.setup_label = QLabel("")
        self.setup_label.setObjectName("footer")
        self.setup_label.setWordWrap(True)
        self.root_layout.addStretch(1)
        self.root_layout.addWidget(self.status_label)
        self.root_layout.addWidget(self.error_label)
        self.root_layout.addWidget(self.setup_label)

        self.apply_metrics(self.base_width, self.base_height)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(settings.refresh_seconds * 1000)
        self.refresh_timer.timeout.connect(self.refresh_payload)
        self.refresh_timer.start()

    def apply_theme(self, theme_name: str) -> None:
        self.active_theme_name = theme_name
        self.theme = THEMES[theme_name]
        self.apply_metrics(max(self.width(), 1), max(self.height(), 1))

    def toggle_theme(self) -> None:
        next_theme = "light" if self.active_theme_name == "dark" else "dark"
        self.theme_mode = next_theme
        self.apply_theme(next_theme)

    def update_setup_qr(self, setup_url: str) -> None:
        qr_size = scaled(96, self.ui_scale, 76)
        qr = qrcode.QRCode(border=1, box_size=8)
        qr.add_data(setup_url)
        qr.make(fit=True)
        image = qr.make_image(
            fill_color=self.theme["qr_fg"],
            back_color=self.theme["qr_bg"],
        ).convert("RGB")
        image = image.resize((qr_size, qr_size))
        data = image.tobytes("raw", "RGB")
        qimage = QImage(
            data,
            image.width,
            image.height,
            image.width * 3,
            QImage.Format.Format_RGB888,
        )
        self.setup_qr.setPixmap(QPixmap.fromImage(qimage.copy()))
        self.setup_qr.setFixedSize(qr_size, qr_size)

    def apply_metrics(self, width: int, height: int) -> None:
        scale = min(width / 480, height / 800)
        self.ui_scale = max(0.84, min(scale, 1.18))
        self.compact_mode = height <= 360
        self.visible_upcoming_limit = (
            1 if self.compact_mode else len(self.upcoming_cards)
        )
        self.setStyleSheet(dashboard_stylesheet(self.ui_scale, self.theme))

        self.root_layout.setContentsMargins(
            scaled(18 if self.compact_mode else 24, self.ui_scale, 12),
            scaled(14 if self.compact_mode else 20, self.ui_scale, 10),
            scaled(18 if self.compact_mode else 24, self.ui_scale, 12),
            scaled(14 if self.compact_mode else 20, self.ui_scale, 10),
        )
        self.root_layout.setSpacing(
            scaled(10 if self.compact_mode else 14, self.ui_scale, 8)
        )
        self.header_layout.setSpacing(scaled(12, self.ui_scale, 8))
        self.header_text_layout.setSpacing(scaled(4, self.ui_scale, 2))
        self.clock_layout.setSpacing(0)
        self.clock_right.setSpacing(scaled(6, self.ui_scale, 4))
        self.text_layout.setSpacing(
            scaled(6 if self.compact_mode else 8, self.ui_scale, 4)
        )
        self.upcoming_layout.setSpacing(
            scaled(8 if self.compact_mode else 10, self.ui_scale, 6)
        )
        self.setup_layout.setContentsMargins(
            scaled(16, self.ui_scale, 12),
            scaled(16, self.ui_scale, 12),
            scaled(16, self.ui_scale, 12),
            scaled(16, self.ui_scale, 12),
        )
        self.setup_layout.setSpacing(scaled(14, self.ui_scale, 10))
        self.setup_text_layout.setSpacing(scaled(4, self.ui_scale, 3))
        self.setup_card.setStyleSheet(
            "QFrame#setupCard {"
            f"background-color: {self.theme['surface_alt']};"
            f"border: 1px solid {self.theme['line']};"
            f"border-radius: {scaled(18, self.ui_scale, 14)}px;"
            "}"
        )

        portrait_stack = width <= 520 or height > width
        direction = (
            QBoxLayout.Direction.TopToBottom
            if portrait_stack
            else QBoxLayout.Direction.LeftToRight
        )
        self.hero_layout.setDirection(direction)
        self.hero_layout.setContentsMargins(
            scaled(18, self.ui_scale, 14),
            scaled(18, self.ui_scale, 14),
            scaled(18, self.ui_scale, 14),
            scaled(18, self.ui_scale, 14),
        )
        self.hero_layout.setSpacing(scaled(14, self.ui_scale, 10))

        radius = scaled(22, self.ui_scale, 16)
        self.hero_frame.setStyleSheet(
            "QFrame#heroFrame {"
            f"background-color: {self.theme['surface']};"
            f"border: 1px solid {self.theme['line']};"
            f"border-radius: {radius}px;"
            "}"
        )
        self.ring_widget.set_scale(self.ui_scale)
        self.ring_widget.apply_theme(self.theme)
        for card in self.upcoming_cards:
            card.apply_scale(self.ui_scale)
            card.apply_theme(self.theme)
        self.upcoming_title.setVisible(not self.compact_mode)
        self.setup_card.setVisible(not self.compact_mode)
        self.status_label.setVisible(not self.compact_mode)
        self.error_label.setVisible(
            not self.compact_mode and bool(self.error_label.text())
        )
        self.setup_label.setVisible(
            not self.compact_mode and bool(self.setup_label.text())
        )
        self.theme_button.setText(
            "Light theme" if self.active_theme_name == "dark" else "Dark theme"
        )

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
        accent = accent_color(payload)
        self.clock_label.setText(payload["clock"])
        self.date_label.setText(payload["dateLabel"])
        self.heading_label.setText(payload["heading"])
        self.subheading_label.setText(payload["subheading"])
        self.current_title_label.setText(payload["currentTitle"])
        self.current_subtitle_label.setText(payload["currentSubtitle"])
        self.ring_widget.set_state(
            payload["remainingMinutes"],
            payload["ringLabel"],
            payload["progress"],
            accent,
        )

        next_event = payload.get("nextEvent")
        if next_event:
            self.next_event_label.setText(
                f"Next up: {next_event['title']}  |  {next_event['range']}"
            )
        else:
            self.next_event_label.setText("No follow-up event scheduled")

        upcoming = payload.get("upcoming", [])
        for index, card in enumerate(self.upcoming_cards):
            if index >= self.visible_upcoming_limit:
                card.setVisible(False)
                continue
            if index < len(upcoming):
                card.setVisible(True)
                card.set_event(upcoming[index])
                continue
            if index == 0 and not upcoming:
                card.setVisible(True)
                card.set_event(None)
                continue
            card.setVisible(False)

        provider_items = []
        for provider in payload.get("providers", []):
            if provider["connected"]:
                state = "connected"
            elif provider["configured"]:
                state = "ready"
            else:
                state = "off"
            provider_items.append(f"{provider['displayName']}: {state}")
        provider_text = " | ".join(provider_items) or "No providers configured"
        if payload.get("mockMode"):
            provider_text = "Mock mode enabled | " + provider_text
        self.status_label.setText(provider_text)
        self.status_label.setVisible(not self.compact_mode)

        errors = payload.get("errors", [])
        self.error_label.setText(
            "Provider errors: " + " | ".join(errors) if errors else ""
        )
        self.error_label.setVisible(not self.compact_mode and bool(errors))
        setup_url = payload.get("setupUrl", settings.base_url)
        self.setup_url.setText(
            "<a href=\""
            + setup_url
            + "\" style=\"color: "
            + self.theme["available"]
            + "; text-decoration: none;\">"
            + setup_url
            + "</a>"
        )
        self.update_setup_qr(setup_url)
        self.setup_label.setText(
            "Scan to open provider setup from another device"
        )
        self.setup_card.setVisible(not self.compact_mode)
        self.setup_label.setVisible(not self.compact_mode)


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
