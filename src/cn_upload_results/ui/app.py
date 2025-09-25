"""Bootstrapper for the PySide6 desktop application."""
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication, QDialog

from cn_upload_results.config.settings import get_settings
from cn_upload_results.ui.auth import SupabaseAuthService
from cn_upload_results.ui.login import LoginDialog
from cn_upload_results.ui.main_window import MainWindow

LOGGER = logging.getLogger(__name__)


def run_ui() -> None:
    """Launch the desktop workflow."""

    app = QApplication.instance() or QApplication(sys.argv)
    settings = get_settings()

    auth_service = SupabaseAuthService(
        url=str(settings.supabase_url),
        anon_key=settings.supabase_anon_key,
    )
    login = LoginDialog(auth_service)
    if login.exec() != QDialog.Accepted:
        LOGGER.info("Login cancelled; exiting UI")
        return

    window = MainWindow(settings=settings)
    window.show()
    app.exec()
