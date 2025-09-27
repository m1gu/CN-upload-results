"""Reusable overlay widget to show blocking loading status."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QTimer, Qt, QSize
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SpinnerWidget(QWidget):
    """Simple spinner animation drawn with QPainter."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._timer.start(80)
        self.setFixedSize(64, 64)

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(64, 64)

    def _advance(self) -> None:
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self._angle)
        radius = min(self.width(), self.height()) / 2 - 6

        for step in range(12):
            opacity = max(0.15, 1.0 - step * 0.08)
            color = QColor("#2ecc71")
            color.setAlphaF(opacity)
            pen = QPen(color, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(0, radius, 0, radius - 18)
            painter.rotate(30)


class LoadingOverlay(QWidget):
    """Semi-transparent overlay with progress animation and status text."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 180);")
        self.setVisible(False)

        if parent is not None:
            parent.installEventFilter(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(18)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._spinner = SpinnerWidget(self)
        layout.addWidget(self._spinner)

        self._status = QLabel("", self)
        self._status.setWordWrap(True)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet("color: white; font-size: 16px;")
        layout.addWidget(self._status)

    def eventFilter(self, watched, event):  # type: ignore[override]
        if watched is self.parent() and event.type() == QEvent.Type.Resize:
            self._resize_to_parent()
        return super().eventFilter(watched, event)

    def show_overlay(self, message: str | None = None) -> None:
        if message:
            self.set_status(message)
        self._resize_to_parent()
        self.setVisible(True)
        self.raise_()

    def hide_overlay(self) -> None:
        self.setVisible(False)

    def set_status(self, message: str) -> None:
        self._status.setText(message)

    def _resize_to_parent(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.setGeometry(0, 0, parent.width(), parent.height())
