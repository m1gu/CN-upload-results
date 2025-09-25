"""Login dialog for the desktop workflow."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from cn_upload_results.ui.auth import SupabaseAuthService


class LoginDialog(QDialog):
    """Collects credentials and performs Supabase authentication."""

    def __init__(self, auth_service: SupabaseAuthService, parent=None) -> None:
        super().__init__(parent)
        self._auth_service = auth_service
        self._status: Optional[QLabel] = None
        self._email_input: Optional[QLineEdit] = None
        self._password_input: Optional[QLineEdit] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Iniciar sesion")
        self.setModal(True)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        email_input = QLineEdit(self)
        email_input.setPlaceholderText("correo@empresa.com")
        email_input.setClearButtonEnabled(True)
        form.addRow("Email", email_input)
        self._email_input = email_input

        password_input = QLineEdit(self)
        password_input.setEchoMode(QLineEdit.Password)
        password_input.setPlaceholderText("Contrasena")
        form.addRow("Password", password_input)
        self._password_input = password_input

        layout.addLayout(form)

        status_label = QLabel("Ingrese sus credenciales para continuar", self)
        status_label.setWordWrap(True)
        layout.addWidget(status_label)
        self._status = status_label

        button_box = QDialogButtonBox(Qt.Horizontal, self)
        login_button = QPushButton("Entrar", self)
        login_button.clicked.connect(self._handle_submit)
        button_box.addButton(login_button, QDialogButtonBox.AcceptRole)
        cancel_button = QPushButton("Cancelar", self)
        cancel_button.clicked.connect(self.reject)
        button_box.addButton(cancel_button, QDialogButtonBox.RejectRole)

        layout.addWidget(button_box)

    def _handle_submit(self) -> None:
        if not self._email_input or not self._password_input:
            return

        email = self._email_input.text().strip()
        password = self._password_input.text().strip()
        if not email or not password:
            self._set_status("Ingrese email y password")
            return

        try:
            self._auth_service.sign_in(email=email, password=password)
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Error de autenticacion: {exc}")
            return

        self.accept()

    def _set_status(self, message: str) -> None:
        if self._status:
            self._status.setText(message)
