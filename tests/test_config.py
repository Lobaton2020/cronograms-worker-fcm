"""Tests for app.config."""

import os
from pathlib import Path

import pytest


@pytest.fixture
def env_file(tmp_path):
    """Create a temporary .env file and return its path."""
    p = tmp_path / ".env"
    p.write_text(
        "DB_HOST=10.0.0.5\n"
        "DB_PORT=3307\n"
        "DB_NAME=custom_db\n"
        "DB_USER=alice\n"
        "DB_PASSWORD=s3cr3t\n"
        "GOOGLE_APPLICATION_CREDENTIALS=/custom/path.json\n"
        "APP_TIMEZONE=UTC\n"
    )
    return str(p)


def test_load_config_uses_mounted_env_file(mocker):
    """When ENV_FILE is set, the explicit path is used."""
    mocker.patch.dict(os.environ, {
        "ENV_FILE": "/app/.env",
        "DB_HOST": "k8s-host",
        "DB_NAME": "tomanotas",
        "DB_PASSWORD": "from-secret",
    }, clear=False)
    from app.config import load_config
    cfg = load_config()
    assert cfg.db_host == "k8s-host"
    assert cfg.db_name == "tomanotas"
    assert cfg.db_password == "from-secret"


def test_load_config_defaults(mocker):
    """When no env vars are set, defaults kick in."""
    mocker.patch.dict(os.environ, {}, clear=True)
    from app.config import load_config
    cfg = load_config()
    assert cfg.db_host == "127.0.0.1"
    assert cfg.db_port == 3306
    assert cfg.db_name == "tomanotas"
    assert cfg.db_user == "root"
    assert cfg.db_password == ""
    assert cfg.google_application_credentials == "/secrets/firebase-sa.json"
    assert cfg.timezone == "America/Bogota"


def test_load_config_from_root_env_file(env_file, monkeypatch):
    """When .env exists at the project root, values are loaded."""
    # Run the worker with CWD pointing to the dir containing the .env
    monkeypatch.chdir(Path(env_file).parent)
    monkeypatch.delenv("ENV_FILE", raising=False)
    # Clear db-related env vars so the .env is the source
    for k in ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD",
              "GOOGLE_APPLICATION_CREDENTIALS", "APP_TIMEZONE"]:
        monkeypatch.delenv(k, raising=False)

    # Reload config to pick up the new .env
    from dotenv import load_dotenv
    load_dotenv(env_file, override=True)

    from app.config import load_config
    cfg = load_config()
    assert cfg.db_host == "10.0.0.5"
    assert cfg.db_port == 3307
    assert cfg.db_name == "custom_db"
    assert cfg.db_user == "alice"
    assert cfg.db_password == "s3cr3t"
    assert cfg.google_application_credentials == "/custom/path.json"
    assert cfg.timezone == "UTC"


def test_database_url(mocker):
    mocker.patch.dict(os.environ, {
        "DB_HOST": "1.2.3.4",
        "DB_PORT": "3306",
        "DB_NAME": "x",
        "DB_USER": "u",
        "DB_PASSWORD": "p",
    }, clear=False)
    from app.config import load_config
    cfg = load_config()
    assert cfg.database_url == "mysql+pymysql://u:p@1.2.3.4:3306/x"
