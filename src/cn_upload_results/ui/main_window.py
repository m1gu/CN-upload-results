
"""Main application window for orchestrating the workflow."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

from cn_upload_results.config.settings import AppSettings
from cn_upload_results.parsers.excel import parse_workbook
from cn_upload_results.ui.loading_overlay import LoadingOverlay
from cn_upload_results.ui.preview import PreviewDialog
from cn_upload_results.ui.publish_worker import PublishWorker
from cn_upload_results.ui.upload import UploadWidget
from cn_upload_results.workflows.upload import UploadOutcome


class MainWindow(QMainWindow):
    """Hosts the upload and preview flow."""

    def __init__(self, *, settings: AppSettings, user_email: Optional[str] = None, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._user_email = user_email
        self._current_file: Optional[Path] = None
        self._upload_widget = UploadWidget(self)
        self._upload_widget.file_selected.connect(self._on_file_selected)
        self._upload_widget.process_requested.connect(self._on_process_requested)
        self.setCentralWidget(self._upload_widget)
        self.setWindowTitle("QBench CN Uploader")
        self.resize(640, 480)

        self._overlay = LoadingOverlay(self)
        self._publish_thread: Optional[QThread] = None
        self._publish_worker: Optional[PublishWorker] = None

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

        overlay_message = "Simulando coincidencias con QBench..." if getattr(self._settings, "dry_run", False) else "Guardando en QBench..."
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


    def _handle_worker_success(self, outcome: UploadOutcome) -> None:
        self._overlay.set_status("Proceso completado")
        self._hide_overlay()

        summary = outcome.summary_text()
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
        message = "\n".join(message_lines)

        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(message)
        box.setInformativeText(summary)
        box.exec()

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
