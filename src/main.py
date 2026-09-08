import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app_info import APP_NAME, APP_ORGANIZATION, APP_VERSION
from runtime import configure_logging, install_exception_hook, install_qt_message_logging


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--smoke-test", action="store_true", help="Open and close the UI automatically")
    parser.add_argument("--log-dir", type=Path, help="Override the application log directory")
    parser.add_argument("--version", action="version", version=f"%(prog)s {APP_VERSION}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(argv) if argv is not None else sys.argv[1:])
    if args.smoke_test:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    log_path = configure_logging(args.log_dir)
    install_exception_hook(log_path)

    from PyQt6.QtCore import QSettings, QStandardPaths, QTimer
    from PyQt6.QtWidgets import QApplication

    from app.main_window import MainWindow

    if args.smoke_test:
        QStandardPaths.setTestModeEnabled(True)

    app = QApplication([sys.argv[0]])
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_ORGANIZATION)
    install_qt_message_logging()

    logger = logging.getLogger("startup")
    logger.info("Starting %s %s with Python %s", APP_NAME, APP_VERSION, sys.version.split()[0])

    settings = None
    if args.smoke_test:
        settings = QSettings(str(log_path.parent / "smoke-settings.ini"), QSettings.Format.IniFormat)
    window = MainWindow(log_path=log_path, settings=settings)
    window.show()
    logger.info("Main window visible: %s", window.isVisible())

    if args.smoke_test:
        QTimer.singleShot(350, app.quit)

    exit_code = app.exec()
    logger.info("Application stopped with exit code %s", exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
