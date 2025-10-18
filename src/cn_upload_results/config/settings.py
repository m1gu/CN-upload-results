"""Application settings via environment variables."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

LOGGER = logging.getLogger(__name__)


def _resolve_env_file() -> str | None:
    """Locate the bundled .env file both in dev mode and within a PyInstaller build."""

    search_paths: list[Path] = []

    if getattr(sys, "frozen", False):
        base_dir = Path(getattr(sys, "_MEIPASS", Path.cwd()))
        search_paths.append(base_dir / ".env")
        search_paths.append(Path(sys.executable).resolve().parent / ".env")

    module_root = Path(__file__).resolve()
    for _ in range(3):
        module_root = module_root.parent
    search_paths.append(module_root / ".env")
    search_paths.append(Path.cwd() / ".env")

    for candidate in search_paths:
        if candidate.is_file():
            return str(candidate)

    LOGGER.warning("No .env file found; relying solely on environment variables.")
    return None


class AppSettings(BaseSettings):
    """Application settings managed via environment variables."""

    model_config = SettingsConfigDict(
        env_file=_resolve_env_file(),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    environment: Literal["sandbox", "production"] = "sandbox"
    qbench_base_url: HttpUrl = "https://sandbox.qbench.net/api"
    qbench_token_url: HttpUrl | None = None
    qbench_client_id: str = ""
    qbench_client_secret: str = ""
    skip_processed_tests: bool = True
    dry_run: bool = False
    supabase_url: HttpUrl
    supabase_anon_key: str
    supabase_service_role_key: str

    @property
    def qbench_token_endpoint(self) -> str:
        """Compute the OAuth token endpoint from the provided base URL."""

        if self.qbench_token_url:
            return str(self.qbench_token_url)

        parsed = urlparse(str(self.qbench_base_url))
        base = parsed._replace(path="", params="", query="", fragment="")
        host = base.geturl().rstrip("/")
        return f"{host}/oauth/token"

    @property
    def is_production(self) -> bool:
        """Boolean helper for environment-aware logic."""

        return self.environment == "production"


def get_settings() -> AppSettings:
    """Factory that loads settings with environment overrides."""

    return AppSettings()
