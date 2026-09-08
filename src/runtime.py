from __future__ import annotations

import faulthandler
import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app_info import APP_NAME, APP_SLUG

_fault_stream = None


def default_log_dir() -> Path:
    """Return a user-writable, platform-appropriate log directory."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / APP_NAME
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base / APP_NAME / "Logs"
    state_home = os.environ.get("XDG_STATE_HOME")
    base = Path(state_home) if state_home else Path.home() / ".local" / "state"
    return base / APP_SLUG / "logs"


def configure_logging(log_dir: str | Path | None = None) -> Path:
    directory = Path(log_dir).expanduser().resolve() if log_dir else default_log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / "application.log"

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    if sys.stderr is not None:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)

    logging.captureWarnings(True)

    global _fault_stream
    if _fault_stream is not None:
        faulthandler.disable()
        _fault_stream.close()
    _fault_stream = (directory / "native-crash.log").open("a", encoding="utf-8")
    faulthandler.enable(file=_fault_stream, all_threads=True)
    return log_path


def install_exception_hook(log_path: Path) -> None:
    """Log uncaught Python errors and keep Qt slot exceptions visible to the user."""
    previous_hook = sys.excepthook

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            previous_hook(exc_type, exc_value, exc_traceback)
            return

        details = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logging.getLogger("crash").critical("Unhandled exception\n%s", details)

        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None,
                    "Application Error",
                    "An unexpected error occurred. Details were written to the application log:\\n\\n"
                    f"{log_path}\n\n{exc_value}",
                )
                return
        except Exception:
            logging.getLogger("crash").exception("Could not display the crash dialog")

        previous_hook(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_exception


def install_qt_message_logging() -> None:
    """Forward Qt warnings and errors to the application log."""
    from PyQt6.QtCore import QtMsgType, qInstallMessageHandler

    levels = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }

    def qt_message_handler(message_type, context, message):
        category = getattr(context, "category", None) or "qt"
        logging.getLogger(category).log(levels.get(message_type, logging.INFO), message)

    qInstallMessageHandler(qt_message_handler)
