"""Application configuration loaded from a .env file.

Local development: place a `.env` file at the project root; the worker will
find it via `python-dotenv.find_dotenv()`.

Production (Kubernetes): the CronJob mounts the `.env` at `/app/.env` from a
Secret (same pattern as TomaNotas, cronogramas-mcp, manejo-finanzas-mcp).
"""

import os
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv

FALLBACK_ENV_PATH = "/app/.env"


def _resolve_env_path() -> str:
    """Resolve the .env path.

    Order:
      1. ENV_FILE environment variable (explicit override).
      2. .env in current working directory or any parent directory (local dev).
      3. /app/.env (production mount point).
    """
    explicit = os.environ.get("ENV_FILE")
    if explicit:
        return explicit
    found = find_dotenv(usecwd=True)
    if found:
        return found
    return FALLBACK_ENV_PATH


# Load .env once at import time.
load_dotenv(_resolve_env_path(), override=False)


@dataclass(frozen=True)
class Config:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    google_application_credentials: str
    timezone: str

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


def load_config() -> Config:
    """Return the current configuration from environment variables."""
    return Config(
        db_host=os.environ.get("DB_HOST", "127.0.0.1"),
        db_port=int(os.environ.get("DB_PORT", "3306")),
        db_name=os.environ.get("DB_NAME", "tomanotas"),
        db_user=os.environ.get("DB_USER", "root"),
        db_password=os.environ.get("DB_PASSWORD", ""),
        google_application_credentials=os.environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS", "/secrets/firebase-sa.json"
        ),
        timezone=os.environ.get("APP_TIMEZONE", "America/Bogota"),
    )
