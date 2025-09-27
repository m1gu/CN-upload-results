"""Worker that runs the publish workflow without blocking the UI."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot

from cn_upload_results.config.settings import AppSettings
from cn_upload_results.services.persistence import (
    build_default_qbench_payload,
    persist_run_to_supabase,
)
from cn_upload_results.workflows.upload import run_upload


class PublishWorker(QObject):
    """Executes the QBench + Supabase workflow in a background thread."""

    progress = Signal(str)
    success = Signal(int)
    error = Signal(str)
    finished = Signal()

    def __init__(
        self,
        *,
        settings: AppSettings,
        excel_path: Path,
        user_email: Optional[str],
    ) -> None:
        super().__init__()
        self._settings = settings
        self._excel_path = Path(excel_path)
        self._user_email = user_email

    @Slot()
    def run(self) -> None:
        try:
            self.progress.emit("Guardando en QBench…")
            try:
                extraction = run_upload(self._excel_path)
            except Exception as exc:  # noqa: BLE001
                self.error.emit(f"Fallo al subir resultados a QBench: {exc}")
                return

            try:
                self.progress.emit("Guardando datos en Supabase…")
                qbench_summary = build_default_qbench_payload(extraction)
                qbench_summary["environment"] = self._settings.environment
                persist_run_to_supabase(
                    settings=self._settings,
                    extraction=extraction,
                    excel_path=self._excel_path,
                    qbench_payload=qbench_summary,
                    created_by=self._user_email,
                )
            except Exception as exc:  # noqa: BLE001
                self.error.emit(f"No se pudo guardar el respaldo en Supabase: {exc}")
                return

            self.progress.emit("Proceso completado")
            self.success.emit(len(extraction.samples))
        finally:
            self.finished.emit()
