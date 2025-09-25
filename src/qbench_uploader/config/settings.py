"""Application settings and environment management."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Typed configuration loaded from environment variables."""

    qbench_base_url: str = "https://sandbox.qbench.net/api"
    qbench_api_key: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


def load_settings() -> Settings:
    """Build a Settings instance."""
    return Settings()
