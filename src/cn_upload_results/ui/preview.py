"""Preview dialog to review parsed data before publishing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from cn_upload_results.domain.models import (
    AREA_RESULT_SUFFIX,
    COMPONENT_ORDER,
    SampleQuantification,
    WorkbookExtraction,
)


@dataclass
class RowDefinition:
    label: str
    value_factory: Callable[[SampleQuantification], Optional[float]]
    key_factory: Callable[[SampleQuantification], str]


class PreviewDialog(QDialog):
    """Shows parsed samples so the user can confirm before uploading."""

    def __init__(self, extraction: WorkbookExtraction, parent=None) -> None:
        super().__init__(parent)
        self._extraction = extraction
        self.setWindowTitle("Previsualizar datos")
        self.resize(1100, 640)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 24)
        layout.setSpacing(18)

        summary = QLabel(
            f"Run {self._extraction.metadata.run_date} - {len(self._extraction.samples)} tests",
            self,
        )
        summary.setProperty("role", "hint")
        layout.addWidget(summary)

        table = QTableWidget(self)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)

        columns = list(self._ordered_samples(self._extraction.samples))
        headers = ["Campo"] + [sample.column_header or sample.sample_id for sample in columns]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        rows = self._build_rows()
        table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            table.setItem(row_index, 0, QTableWidgetItem(row.label))
            for column_index, sample in enumerate(columns, start=1):
                value = row.value_factory(sample)
                label = row.key_factory(sample)
                table.setItem(row_index, column_index, _format_item(label, value))

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

    def _build_rows(self) -> List[RowDefinition]:
        rows: List[RowDefinition] = []
        rows.extend(self._component_rows())
        rows.extend(self._metadata_rows())
        rows.extend(self._area_rows())
        return rows

    def _component_rows(self) -> Iterable[RowDefinition]:
        for component in COMPONENT_ORDER:
            yield RowDefinition(
                label=component.upper(),
                value_factory=lambda sample, component=component: sample.components.get(component),
                key_factory=lambda sample, component=component: f"{component}_{sample.test_index}",
            )

    def _metadata_rows(self) -> Iterable[RowDefinition]:
        yield RowDefinition(
            label="sample_mass",
            value_factory=lambda sample: sample.sample_mass_mg,
            key_factory=lambda sample: f"sample_mass_{sample.test_index}",
        )
        yield RowDefinition(
            label="dilution",
            value_factory=lambda sample: sample.dilution,
            key_factory=lambda sample: f"dilution_{sample.test_index}",
        )
        yield RowDefinition(
            label="serving_mass_g",
            value_factory=lambda sample: sample.serving_mass_g,
            key_factory=lambda sample: f"serving_mass_g_{sample.test_index}",
        )
        yield RowDefinition(
            label="servings_per_package",
            value_factory=lambda sample: sample.servings_per_package,
            key_factory=lambda sample: f"servings_per_package_{sample.test_index}",
        )
        yield RowDefinition(
            label="",  # visual spacer
            value_factory=lambda sample: None,
            key_factory=lambda sample: "",
        )

    def _area_rows(self) -> Iterable[RowDefinition]:
        for component in COMPONENT_ORDER:
            label = f"{component}{AREA_RESULT_SUFFIX}"
            yield RowDefinition(
                label=label,
                value_factory=lambda sample, component=component: sample.area_results.get(component),
                key_factory=lambda sample, component=component: f"{component}{AREA_RESULT_SUFFIX}_{sample.test_index}",
            )

    @staticmethod
    def _ordered_samples(samples: List[SampleQuantification]) -> List[SampleQuantification]:
        return sorted(
            samples,
            key=lambda sample: (sample.base_sample_id, sample.test_index, sample.sample_id),
        )


def _format_item(key: str, value: Optional[float]) -> QTableWidgetItem:
    if value is None:
        return QTableWidgetItem("")
    item = QTableWidgetItem(_format_numeric(value))
    if key:
        item.setToolTip(key)
    return item


def _format_numeric(value: float) -> str:
    text = f"{value:.6f}"
    return text.rstrip("0").rstrip(".")
