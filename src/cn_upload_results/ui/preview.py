"""Preview dialog to review parsed data before publishing.""" 
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from cn_upload_results.domain.models import SampleQuantification, WorkbookExtraction


class PreviewDialog(QDialog):
    """Shows parsed samples so the user can confirm before uploading."""

    def __init__(self, extraction: WorkbookExtraction, parent=None) -> None:
        super().__init__(parent)
        self._extraction = extraction
        self.setWindowTitle("Previsualizar datos")
        self.resize(820, 600)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 24)
        layout.setSpacing(18)

        summary = QLabel(
            f"Run {self._extraction.metadata.run_date} - {len(self._extraction.samples)} muestras",
            self,
        )
        summary.setProperty("role", "hint")
        layout.addWidget(summary)

        table = QTableWidget(self)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(
            [
                "Sample",
                "Batches",
                "Componentes llenos",
                "Sample Mass (mg)",
                "Dilution",
            ]
        )

        table.setRowCount(len(self._extraction.samples))
        for row_index, sample in enumerate(self._extraction.samples):
            self._populate_row(table, row_index, sample)
        table.resizeColumnsToContents()
        layout.addWidget(table)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok,
            parent=self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Publicar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cerrar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _populate_row(table: QTableWidget, row_index: int, sample: SampleQuantification) -> None:
        components_filled = sum(1 for value in sample.components.values() if value is not None)
        table.setItem(row_index, 0, QTableWidgetItem(sample.sample_id))
        table.setItem(row_index, 1, QTableWidgetItem(", ".join(sample.batch_numbers)))
        table.setItem(row_index, 2, QTableWidgetItem(str(components_filled)))
        table.setItem(
            row_index,
            3,
            QTableWidgetItem("" if sample.sample_mass_mg is None else f"{sample.sample_mass_mg:.2f}"),
        )
        table.setItem(
            row_index,
            4,
            QTableWidgetItem("" if sample.dilution is None else f"{sample.dilution:.2f}"),
        )
