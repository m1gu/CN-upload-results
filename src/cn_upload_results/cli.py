"""Command-line entry for launching the desktop application."""
from __future__ import annotations

from cn_upload_results.ui.app import run_ui


def main() -> None:
    """Entry point that delegates to the PySide6 UI."""

    run_ui()
