"""Authentication plumbing for the desktop application."""
from __future__ import annotations

from typing import Any, Dict, Optional

from supabase import Client, create_client


class SupabaseAuthService:
    """Encapsulates Supabase authentication flows for the UI."""

    def __init__(self, *, url: str, anon_key: str) -> None:
        self._client: Client = create_client(url, anon_key)

    def sign_in(self, *, email: str, password: str) -> Dict[str, Any]:
        response = self._client.auth.sign_in_with_password(
            {
                "email": email,
                "password": password,
            }
        )
        return response.model_dump() if hasattr(response, "model_dump") else response

    def get_session(self) -> Optional[Dict[str, Any]]:
        session = self._client.auth.get_session()
        if session is None:
            return None
        return session.model_dump() if hasattr(session, "model_dump") else session
