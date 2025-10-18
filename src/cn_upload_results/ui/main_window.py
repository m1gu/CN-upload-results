
"""Main application window for orchestrating the workflow."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from cn_upload_results.config.settings import AppSettings
from cn_upload_results.parsers.excel import parse_workbook
from cn_upload_results.ui.loading_overlay import LoadingOverlay
from cn_upload_results.ui.preview import PreviewDialog
from cn_upload_results.ui.publish_worker import PublishWorker
from cn_upload_results.ui.upload import UploadWidget
from cn_upload_results.workflows.upload import UploadOutcome

LOGGER = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Hosts the upload and preview flow."""

    def __init__(self, *, settings: AppSettings, user_email: Optional[str] = None, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._user_email = user_email
        self._current_file: Optional[Path] = None
        self._container = QWidget(self)
        root_layout = QVBoxLayout(self._container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._upload_widget = UploadWidget(self._container)
        self._upload_widget.file_selected.connect(self._on_file_selected)
        self._upload_widget.process_requested.connect(self._on_process_requested)
        root_layout.addWidget(self._upload_widget)

        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(24, 0, 24, 16)
        footer_layout.addStretch()

        self._dry_run_checkbox = QCheckBox("Dry run mode", self._container)
        self._dry_run_checkbox.setChecked(bool(getattr(self._settings, "dry_run", False)))
        self._dry_run_checkbox.toggled.connect(self._handle_dry_run_toggle)
        self._dry_run_checkbox.setToolTip("Cuando esta activo no se enviaran cambios a QBench ni Supabase.")
        footer_layout.addWidget(self._dry_run_checkbox)
        root_layout.addLayout(footer_layout)

        self.setCentralWidget(self._container)
        self.setWindowTitle("QBench CN Uploader")
        self.resize(640, 480)

        self._overlay = LoadingOverlay(self)
        self._publish_thread: Optional[QThread] = None
        self._publish_worker: Optional[PublishWorker] = None

        self._handle_dry_run_toggle(self._dry_run_checkbox.isChecked())

    def _on_file_selected(self, path: Path) -> None:
        self._current_file = path

    def _on_process_requested(self) -> None:
        if self._publish_thread and self._publish_thread.isRunning():
            QMessageBox.information(
                self,
                "Proceso en curso",
                "Ya hay una publicacion en ejecucion. Espere a que finalice antes de iniciar otra.",
            )
            return

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

        dry_run_active = self._dry_run_checkbox.isChecked()
        if hasattr(self._settings, "dry_run"):
            self._settings.dry_run = dry_run_active
        overlay_message = (
            "Simulando coincidencias con QBench..." if dry_run_active else "Guardando en QBench..."
        )
        self._show_overlay(overlay_message)
        self._start_publish_worker()

    def _start_publish_worker(self) -> None:
        if not self._current_file:
            return

        thread = QThread(self)
        worker = PublishWorker(
            settings=self._settings,
            excel_path=self._current_file,
            user_email=self._user_email,
        )
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._handle_worker_progress)
        worker.success.connect(self._handle_worker_success)
        worker.error.connect(self._handle_worker_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_worker_state)

        self._publish_thread = thread
        self._publish_worker = worker
        thread.start()

    def _handle_worker_progress(self, message: str) -> None:
        self._overlay.set_status(message)

    def _handle_dry_run_toggle(self, checked: bool) -> None:
        setattr(self._settings, "dry_run", checked)

        dry_run_value = bool(getattr(self._settings, "dry_run", checked))
        hint = (
            "Modo simulacion activo: no se enviaran datos a QBench ni Supabase."
            if dry_run_value
            else "Modo simulacion desactivado: los cambios se aplicaran en QBench."
        )
        self.statusBar().showMessage(hint, 5000)

    def _handle_worker_success(self, outcome: UploadOutcome) -> None:
        self._overlay.set_status("Proceso completado")
        self._hide_overlay()

        summary = outcome.summary_text()
        title, message = self._build_completion_message(outcome)

        if getattr(outcome, "dry_run", False):
            console_payload = f"{message}\n\n{summary}"
            if LOGGER.isEnabledFor(logging.INFO):
                LOGGER.info("%s", console_payload)
            else:
                # Logging INFO is disabled; echo the dry-run summary to stdout.
                print(console_payload)

        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(message)

        details = QPlainTextEdit(box)
        details.setPlainText(summary)
        details.setReadOnly(True)
        details.setMinimumHeight(220)
        details.setMaximumHeight(320)
        details.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        layout = box.layout()
        if layout is not None:
            layout.addWidget(details, layout.rowCount(), 0, 1, layout.columnCount())

        box.exec()

    def _build_completion_message(self, outcome: UploadOutcome) -> tuple[str, str]:
        if getattr(outcome, "dry_run", False):
            message_lines = [
                "Simulacion completada.",
                f"Samples analizados: {outcome.total_processed_samples()}",
                f"Samples omitidos: {outcome.total_skipped_samples()}",
            ]
            title = "Simulacion completada"
        else:
            message_lines = [
                "Se completo la publicacion.",
                f"Samples actualizados: {outcome.total_processed_samples()}",
                f"Samples omitidos: {outcome.total_skipped_samples()}",
            ]
            title = "Publicacion completa"

        return title, "\n".join(message_lines)

    def _handle_worker_error(self, message: str) -> None:
        self._hide_overlay()
        QMessageBox.critical(self, "Error en publicacion", message)

    def _clear_worker_state(self) -> None:
        self._publish_thread = None
        self._publish_worker = None

    def _show_overlay(self, message: str) -> None:
        self._overlay.show_overlay(message)
        self._process_events()

    def _hide_overlay(self) -> None:
        self._overlay.hide_overlay()
        self._process_events()

    @staticmethod
    def _process_events() -> None:
        QApplication.processEvents()
