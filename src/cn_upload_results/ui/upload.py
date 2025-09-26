"""Upload view for selecting Excel workbooks."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class UploadWidget(QWidget):
    """Widget that lets the user pick a workbook and trigger processing."""

    file_selected = Signal(object)
    process_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._selected_path: Optional[Path] = None
        self._status_label: Optional[QLabel] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 24)
        layout.setSpacing(18)

        status = QLabel("Seleccione un archivo Excel.", self)
        status.setWordWrap(True)
        status.setProperty("role", "hint")
        layout.addWidget(status)
        self._status_label = status

        picker_button = QPushButton("Buscar archivo", self)
        picker_button.clicked.connect(self._open_dialog)
        layout.addWidget(picker_button)

        process_button = QPushButton("Procesar", self)
        process_button.clicked.connect(self._handle_process)
        layout.addWidget(process_button)

        layout.addStretch(1)

    def _open_dialog(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccione el archivo Excel",
            "",
            "Excel Files (*.xlsx *.xlsm)",
        )
        if not file_name:
            return
        path = Path(file_name)
        self._selected_path = path
        self.file_selected.emit(path)
        self._set_status(f"Archivo seleccionado: {path.name}")

    def _handle_process(self) -> None:
        if not self._selected_path:
            self._set_status("Debe seleccionar un archivo antes de procesar")
            return
        self.process_requested.emit()

    def _set_status(self, message: str) -> None:
        if self._status_label:
            self._status_label.setText(message)
