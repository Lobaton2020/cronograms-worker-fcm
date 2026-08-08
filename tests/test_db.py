"""Tests for app.db using SQLite in-memory."""

from datetime import datetime

import pytest
from sqlalchemy import text

from app.db import (
    get_pending_tasks,
    mark_notified,
)


def test_get_pending_tasks_returns_matching_row(session_factory, seed_data):
    seed_data(task_hour=14, task_minute=30)
    with session_factory() as s:
        rows = get_pending_tasks(s, __import__("datetime").date(2026, 8, 8), 14, 30)
    assert len(rows) == 1
    assert rows[0].id == 10
    assert rows[0].description == "Hacer ejercicio"
    assert rows[0].hour == 14
    assert rows[0].minute == 30
    assert rows[0].fcm_token == "tok-123"


def test_get_pending_tasks_excludes_completed(session_factory, seed_data):
    seed_data(task_state=1)  # estado=1 means completed
    with session_factory() as s:
        rows = get_pending_tasks(s, __import__("datetime").date(2026, 8, 8), 14, 30)
    assert len(rows) == 0


def test_get_pending_tasks_excludes_already_notified(session_factory, seed_data):
    seed_data()
    with session_factory() as s:
        s.execute(
            text("UPDATE tarea_cronograma SET notified_at = :now WHERE id_tarea_cronograma_PK = 10"),
            {"now": datetime(2026, 8, 8, 13, 0, 0)},
        )
        s.commit()
        rows = get_pending_tasks(s, __import__("datetime").date(2026, 8, 8), 14, 30)
    assert len(rows) == 0


def test_get_pending_tasks_excludes_wrong_hour(session_factory, seed_data):
    seed_data(task_hour=14, task_minute=30)
    with session_factory() as s:
        rows = get_pending_tasks(s, __import__("datetime").date(2026, 8, 8), 15, 30)
    assert len(rows) == 0


def test_get_pending_tasks_excludes_wrong_minute(session_factory, seed_data):
    seed_data(task_hour=14, task_minute=30)
    with session_factory() as s:
        rows = get_pending_tasks(s, __import__("datetime").date(2026, 8, 8), 14, 31)
    assert len(rows) == 0


def test_get_pending_tasks_excludes_other_date(session_factory, seed_data):
    seed_data(task_date=__import__("datetime").date(2026, 8, 8))
    with session_factory() as s:
        rows = get_pending_tasks(s, __import__("datetime").date(2026, 8, 9), 14, 30)
    assert len(rows) == 0


def test_get_pending_tasks_joins_project_name(session_factory, seed_data):
    seed_data(project_id=99)
    with session_factory() as s:
        rows = get_pending_tasks(s, __import__("datetime").date(2026, 8, 8), 14, 30)
    assert rows[0].project_name == "Proyecto A"


def test_get_pending_tasks_returns_one_per_token(session_factory, seed_data):
    seed_data()
    with session_factory() as s:
        s.execute(text(
            "INSERT INTO fcm_tokens (id_usuario_FK, token, platform, created_at, updated_at) "
            "VALUES (1, 'tok-456', 'android', :now, :now)"
        ), {"now": datetime(2026, 8, 8, 12, 0, 0)})
        s.commit()
        rows = get_pending_tasks(s, __import__("datetime").date(2026, 8, 8), 14, 30)
    # One task per token = 2 rows
    assert len(rows) == 2
    tokens = {r.fcm_token for r in rows}
    assert tokens == {"tok-123", "tok-456"}


def test_mark_notified_marks_and_returns_rowcount(session_factory, seed_data):
    seed_data()
    now = datetime(2026, 8, 8, 19, 30, 0)
    with session_factory() as s:
        rc = mark_notified(s, 10, now)
    assert rc == 1
    with session_factory() as s:
        row = s.execute(text(
            "SELECT notified_at FROM tarea_cronograma WHERE id_tarea_cronograma_PK = 10"
        )).fetchone()
    # SQLite stores datetimes as ISO strings; compare as strings portably
    assert str(row.notified_at) == "2026-08-08 19:30:00"


def test_mark_notified_is_idempotent(session_factory, seed_data):
    """Calling mark_notified twice returns 0 the second time."""
    seed_data()
    now = datetime(2026, 8, 8, 19, 30, 0)
    with session_factory() as s:
        mark_notified(s, 10, now)
    with session_factory() as s:
        rc = mark_notified(s, 10, now)
    assert rc == 0
