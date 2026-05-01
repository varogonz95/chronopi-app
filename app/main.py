from __future__ import annotations

import os
import socket
import sys
import time
from pathlib import Path
from threading import Thread
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    def _load_dotenv_fallback(*args, **kwargs) -> bool:
        del args, kwargs
        return False

    load_dotenv = _load_dotenv_fallback

from PySide6.QtCore import QEvent, QUrl, Qt
from PySide6.QtGui import QFont, QFontDatabase, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from .config import Settings

QWebEngineView: Any = None
QWebEngineSettings: Any = None
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView as _QWebEngineView
    from PySide6.QtWebEngineCore import (
        QWebEngineSettings as _QWebEngineSettings,
    )
    QWebEngineView = _QWebEngineView
    QWebEngineSettings = _QWebEngineSettings
    web_engine_available = True
except ImportError:
    web_engine_available = False

load_dotenv(override=True)
settings = Settings.from_env()
print(f"Loaded settings: {settings!r}", file=sys.stderr)

DEFAULT_FONT_FAMILY = "DejaVu Sans"
APP_FONT_FAMILY = DEFAULT_FONT_FAMILY


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


def _start_backend_server() -> Thread:
    from .auth_server import app as flask_app

    def serve() -> None:
        flask_app.run(
            host=settings.host,
            port=settings.port,
            debug=False,
            use_reloader=False,
        )

    thread = Thread(target=serve, daemon=True)
    thread.start()
    return thread


def _wait_for_backend(host: str, port: int, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(
        f"Backend server did not start on {host}:{port} within {timeout}s"
    )


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


def desired_rotation() -> str:
    return os.getenv("SCREEN_ROTATION", "right").strip().lower()


class WebDashboardWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(settings.ui_label)
        self.setObjectName("root")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.browser = QWebEngineView()
        if QWebEngineSettings is not None:
            self.browser.settings().setAttribute(
                QWebEngineSettings.WebAttribute.JavascriptEnabled,
                True,
            )
            self.browser.settings().setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
                True,
            )

        self.browser.setUrl(QUrl(f"http://127.0.0.1:{settings.port}/"))
        layout.addWidget(self.browser)


class RotatedWindow(QWidget):
    def __init__(
        self,
        content: QWidget,
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
        application = existing_app
    load_app_font(application)
    return application


def main() -> int:
    if not web_engine_available:
        raise RuntimeError(
            "Qt WebEngine is required to render the web dashboard."
        )

    application = create_application()
    _start_backend_server()
    _wait_for_backend("127.0.0.1", settings.port)

    window = WebDashboardWindow()

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
