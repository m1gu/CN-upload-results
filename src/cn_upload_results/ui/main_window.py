"""Main application window for orchestrating the workflow."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
)

from cn_upload_results.config.settings import AppSettings
from cn_upload_results.parsers.excel import parse_workbook
from cn_upload_results.ui.preview import PreviewDialog
from cn_upload_results.ui.upload import UploadWidget
from cn_upload_results.workflows.upload import run_upload


class MainWindow(QMainWindow):
    """Hosts the upload and preview flow."""

    def __init__(self, *, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._current_file: Optional[Path] = None
        self._upload_widget = UploadWidget(self)
        self._upload_widget.file_selected.connect(self._on_file_selected)
        self._upload_widget.process_requested.connect(self._on_process_requested)
        self.setCentralWidget(self._upload_widget)
        self.setWindowTitle("QBench CN Uploader")
        self.resize(600, 400)

    def _on_file_selected(self, path: Path) -> None:
        self._current_file = path

    def _on_process_requested(self) -> None:
        if not self._current_file:
            QMessageBox.warning(self, "Seleccion requerida", "Seleccione un archivo primero")
            return

        try:
            extraction = parse_workbook(self._current_file)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error al leer", f"No se pudo procesar el Excel: {exc}")
            return

        preview = PreviewDialog(extraction, self)
        if preview.exec() != PreviewDialog.Accepted:
            return

        try:
            result = run_upload(self._current_file)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error en publicacion", f"Fallo al subir resultados: {exc}")
            return

        QMessageBox.information(
            self,
            "Publicacion completa",
            f"Se subieron {len(result.samples)} samples a QBench",
        )
