"""Pytest fixtures: in-memory SQLite DB, mocked FCM, fixed Bogota time."""

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, text

from app import db, fcm


SCHEMA_SQL = """
CREATE TABLE Usuario (
    id_usuario_PK INTEGER PRIMARY KEY,
    nombre        TEXT NOT NULL
);

CREATE TABLE cronograma (
    id_cronograma_PK INTEGER PRIMARY KEY,
    id_usuario_FK   INTEGER NOT NULL,
    titulo          TEXT,
    fecha           DATE NOT NULL
);

CREATE TABLE tarea_cronograma (
    id_tarea_cronograma_PK INTEGER PRIMARY KEY,
    id_cronograma_FK      INTEGER NOT NULL,
    descripcion           TEXT NOT NULL,
    hora                  INTEGER NOT NULL,
    minuto                INTEGER NOT NULL,
    estado                INTEGER NOT NULL,
    project_id            INTEGER,
    notified_at           DATETIME
);

CREATE TABLE projects (
    id      INTEGER PRIMARY KEY,
    name    TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    status  INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE fcm_tokens (
    id_fcm_token_PK INTEGER PRIMARY KEY,
    id_usuario_FK   INTEGER NOT NULL,
    token           TEXT NOT NULL UNIQUE,
    platform        TEXT NOT NULL DEFAULT 'android',
    created_at      DATETIME NOT NULL,
    updated_at      DATETIME NOT NULL
);
"""


@pytest.fixture
def in_memory_db():
    """Yield a SQLAlchemy engine backed by SQLite in-memory with the test schema."""
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
    )
    with engine.begin() as conn:
        for stmt in SCHEMA_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(in_memory_db):
    """Return a sessionmaker bound to the in-memory engine."""
    return db.make_session_factory(in_memory_db)


@pytest.fixture
def mock_fcm(mocker):
    """Patch fcm.send and return the mock."""
    mocker.patch.object(fcm, "init_firebase")
    mocked = mocker.patch.object(fcm, "send", return_value="msg-id-xyz")
    return mocked


@pytest.fixture
def fixed_time_now():
    """Datetime in UTC for marking notified_at."""
    return datetime(2026, 8, 8, 19, 30, 0)


@pytest.fixture
def fixed_date_bogota():
    """A deterministic Bogota date."""
    return date(2026, 8, 8)


@pytest.fixture
def fixed_hour_minute():
    """(hour, minute) in Bogota."""
    return (14, 30)


@pytest.fixture
def seed_data(session_factory):
    """Return a callable that inserts a baseline scenario."""

    def _seed(*, task_hour=14, task_minute=30, task_date=None,
              task_desc="Hacer ejercicio", task_state=0, project_id=None,
              token_value="tok-123"):
        if task_date is None:
            task_date = date(2026, 8, 8)
        with session_factory() as s:
            s.execute(text("INSERT INTO Usuario (id_usuario_PK, nombre) VALUES (1, 'Andres')"))
            s.execute(text("INSERT INTO cronograma (id_cronograma_PK, id_usuario_FK, titulo, fecha) "
                           "VALUES (1, 1, 'Rutina', :d)"), {"d": task_date})
            s.execute(text(
                "INSERT INTO tarea_cronograma "
                "(id_tarea_cronograma_PK, id_cronograma_FK, descripcion, hora, minuto, estado, project_id) "
                "VALUES (10, 1, :desc, :h, :m, :state, :proj)"
            ), {"desc": task_desc, "h": task_hour, "m": task_minute,
                 "state": task_state, "proj": project_id})
            if project_id:
                s.execute(text(
                    "INSERT INTO projects (id, name, user_id, status) VALUES (:id, 'Proyecto A', 1, 1)"
                ), {"id": project_id})
            s.execute(text(
                "INSERT INTO fcm_tokens (id_usuario_FK, token, platform, created_at, updated_at) "
                "VALUES (1, :tok, 'android', :now, :now)"
            ), {"tok": token_value, "now": datetime(2026, 8, 8, 12, 0, 0)})
            s.commit()
        return {"task_id": 10, "token": token_value}

    return _seed
