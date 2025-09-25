"""Command-line interface for CN upload automation."""
from __future__ import annotations

import logging
from pathlib import Path

import typer

from cn_upload_results.workflows.upload import run_upload

LOGGER = logging.getLogger(__name__)

app = typer.Typer(help="Automate the upload of CN results to QBench.")


@app.command()
def upload(excel_path: Path) -> None:
    """Process an Excel workbook and push data to QBench and Supabase."""

    LOGGER.info("Processing workbook %s", excel_path)
    extraction = run_upload(excel_path)
    typer.echo(
        f"Uploaded {len(extraction.samples)} samples from run {extraction.metadata.run_date}"  # noqa: E501
    )


@app.command()
def ui() -> None:
    """Launch the desktop interface (PySide6)."""

    from cn_upload_results.ui.app import run_ui

    run_ui()
