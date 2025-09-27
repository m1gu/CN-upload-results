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

    authenticated_email: Optional[str] = None


    def __init__(self, auth_service: SupabaseAuthService, parent=None) -> None:
        super().__init__(parent)
        self._auth_service = auth_service
        self.authenticated_email = None
        self._status: Optional[QLabel] = None
        self._email_input: Optional[QLineEdit] = None
        self._password_input: Optional[QLineEdit] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Iniciar sesion")
        self.setModal(True)
        self.resize(420, 260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 24)
        layout.setSpacing(20)

        title = QLabel("<b>Acceso</b>", self)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(16)

        email_input = QLineEdit(self)
        email_input.setPlaceholderText("Email")
        email_input.setClearButtonEnabled(True)
        email_input.setText("mrodriguezegues@gmail.com")
        form.addRow("Email", email_input)
        self._email_input = email_input

        password_input = QLineEdit(self)
        password_input.setEchoMode(QLineEdit.Password)
        password_input.setPlaceholderText("Contrasena")
        password_input.setText("12345678")
        form.addRow("Password", password_input)
        self._password_input = password_input

        layout.addLayout(form)

        status_label = QLabel("Ingrese sus credenciales para continuar", self)
        status_label.setWordWrap(True)
        status_label.setProperty("role", "hint")
        layout.addWidget(status_label)
        self._status = status_label

        buttons = QDialogButtonBox(Qt.Horizontal, self)
        login_button = QPushButton("Ingresar", self)
        login_button.clicked.connect(self._handle_submit)
        buttons.addButton(login_button, QDialogButtonBox.AcceptRole)
        cancel_button = QPushButton("Cancelar", self)
        cancel_button.clicked.connect(self.reject)
        buttons.addButton(cancel_button, QDialogButtonBox.RejectRole)

        layout.addWidget(buttons)

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

        self.authenticated_email = email
        self.accept()

    def _set_status(self, message: str) -> None:
        if self._status:
            self._status.setText(message)

    @property
    def authenticated_user(self) -> Optional[str]:
        return self.authenticated_email
