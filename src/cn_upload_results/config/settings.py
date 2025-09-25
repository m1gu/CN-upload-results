"""Application settings via environment variables."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application settings managed via environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    environment: Literal["sandbox", "production"] = "sandbox"
    qbench_base_url: HttpUrl = "https://sandbox.qbench.net/api"
    qbench_api_key: str = ""
    supabase_url: HttpUrl
    supabase_anon_key: str
    supabase_service_role_key: str

    @property
    def is_production(self) -> bool:
        """Boolean helper for environment-aware logic."""

        return self.environment == "production"



@lru_cache
def get_settings() -> AppSettings:
    """Factory that loads settings with environment overrides."""

    return AppSettings()
