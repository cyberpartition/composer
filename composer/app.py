"""Start the Composer desktop app."""

from __future__ import annotations

import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

from composer import __version__
from composer.branding import app_icon
from composer.paths import settings_dir
from composer.theme import apply_theme
from composer.window import MainWindow


def main() -> int:
    _install_excepthook()
    if sys.platform == "win32":
        _set_app_id()
    application = QApplication(sys.argv)
    application.setApplicationName("Composer")
    application.setOrganizationName("Composer")
    application.setApplicationDisplayName("Composer")
    application.setApplicationVersion(__version__)
    apply_theme(application)
    icon = app_icon()
    if not icon.isNull():
        application.setWindowIcon(icon)
    window = MainWindow()
    window.show()
    return application.exec()


def _set_app_id() -> None:
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Composer.Desktop.1")
    except Exception:
        pass


def _install_excepthook() -> None:
    def hook(exc_type, exc, tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        log_path = None
        try:
            log_path = settings_dir() / "error.log"
            log_path.write_text(text, encoding="utf-8")
        except Exception:
            log_path = None
        summary = "".join(traceback.format_exception_only(exc_type, exc)).strip() or "Composer ran into a problem."
        if log_path is not None:
            summary += f"\n\nDetails were saved to:\n{log_path}"
        application = QApplication.instance()
        if application is not None:
            try:
                QMessageBox.critical(None, "Composer", summary)
                return
            except Exception:
                pass
        if sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.user32.MessageBoxW(0, summary, "Composer", 0x10)
                return
            except Exception:
                pass
        sys.stderr.write(text)

    sys.excepthook = hook
