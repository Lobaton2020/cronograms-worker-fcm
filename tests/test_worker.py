"""Tests for app.worker orchestrator."""

import logging
from datetime import date, datetime

import pytest
from sqlalchemy import text

from app import worker


@pytest.fixture
def freeze_time(mocker):
    """Freeze 'now in Bogota' to a fixed value."""
    mock_date = date(2026, 8, 8)
    mock_hm = (14, 30)
    mocker.patch("app.worker.current_date_bogota", return_value=mock_date)
    mocker.patch("app.worker.current_hour_minute_bogota", return_value=mock_hm)
    return mock_date, mock_hm


def test_worker_returns_0_on_success(
    session_factory, seed_data, mock_fcm, freeze_time, fixed_time_now, mocker
):
    seed_data(task_hour=14, task_minute=30)
    mocker.patch("app.worker.db.build_engine", return_value=mocker.MagicMock())
    mocker.patch("app.worker.db.make_session_factory", return_value=session_factory)

    rc = worker.run()
    assert rc == 0
    assert mock_fcm.call_count == 1


def test_worker_marks_task_as_notified(
    session_factory, seed_data, mock_fcm, freeze_time, mocker
):
    seed_data(task_hour=14, task_minute=30)
    mocker.patch("app.worker.db.build_engine", return_value=mocker.MagicMock())
    mocker.patch("app.worker.db.make_session_factory", return_value=session_factory)

    worker.run()

    with session_factory() as s:
        row = s.execute(text(
            "SELECT notified_at FROM tarea_cronograma WHERE id_tarea_cronograma_PK = 10"
        )).fetchone()
    assert row.notified_at is not None


def test_worker_does_not_send_twice_for_same_task(
    session_factory, seed_data, mock_fcm, freeze_time, mocker
):
    seed_data(task_hour=14, task_minute=30)
    mocker.patch("app.worker.db.build_engine", return_value=mocker.MagicMock())
    mocker.patch("app.worker.db.make_session_factory", return_value=session_factory)

    worker.run()
    worker.run()  # second run should not pick the already-notified task
    assert mock_fcm.call_count == 1


def test_worker_skips_completed_tasks(
    session_factory, seed_data, mock_fcm, freeze_time, mocker
):
    seed_data(task_hour=14, task_minute=30, task_state=1)
    mocker.patch("app.worker.db.build_engine", return_value=mocker.MagicMock())
    mocker.patch("app.worker.db.make_session_factory", return_value=session_factory)

    rc = worker.run()
    assert rc == 0
    mock_fcm.assert_not_called()


def test_worker_continues_after_partial_failure(
    session_factory, seed_data, mock_fcm, freeze_time, mocker
):
    """If one task fails, the next one should still be processed."""
    # Two tasks at the same hour/minute
    seed_data(task_hour=14, task_minute=30)
    with session_factory() as s:
        s.execute(text(
            "INSERT INTO tarea_cronograma "
            "(id_tarea_cronograma_PK, id_cronograma_FK, descripcion, hora, minuto, estado, project_id) "
            "VALUES (11, 1, 'Otra tarea', 14, 30, 0, NULL)"
        ))
        s.commit()

    call_count = {"n": 0}

    def fake_send(task):
        call_count["n"] += 1
        if task.id == 10:
            raise RuntimeError("simulated FCM failure")
        return "ok"

    mock_fcm.side_effect = fake_send
    mocker.patch("app.worker.db.build_engine", return_value=mocker.MagicMock())
    mocker.patch("app.worker.db.make_session_factory", return_value=session_factory)

    rc = worker.run()
    assert rc == 0  # 0 indicates "no fatal error" per current implementation
    assert call_count["n"] == 2

    # Task 11 should be marked notified, task 10 should NOT be
    with session_factory() as s:
        row10 = s.execute(text(
            "SELECT notified_at FROM tarea_cronograma WHERE id_tarea_cronograma_PK = 10"
        )).fetchone()
        row11 = s.execute(text(
            "SELECT notified_at FROM tarea_cronograma WHERE id_tarea_cronograma_PK = 11"
        )).fetchone()
    assert row10.notified_at is None
    assert row11.notified_at is not None


def test_worker_returns_1_if_firebase_init_fails(
    session_factory, seed_data, freeze_time, mocker
):
    seed_data(task_hour=14, task_minute=30)
    mocker.patch("app.worker.db.build_engine", return_value=mocker.MagicMock())
    mocker.patch("app.worker.db.make_session_factory", return_value=session_factory)
    mocker.patch("app.worker.fcm.init_firebase", side_effect=RuntimeError("no creds"))

    rc = worker.run()
    assert rc == 1


def test_worker_returns_2_on_db_query_failure(
    session_factory, seed_data, freeze_time, mocker
):
    from sqlalchemy.exc import SQLAlchemyError

    seed_data(task_hour=14, task_minute=30)
    mocker.patch("app.worker.db.build_engine", return_value=mocker.MagicMock())
    mocker.patch("app.worker.db.make_session_factory", return_value=session_factory)

    mocker.patch("app.worker.db.get_pending_tasks",
                 side_effect=SQLAlchemyError("boom"))

    rc = worker.run()
    assert rc == 2


def test_worker_no_tasks_returns_0(
    session_factory, seed_data, mock_fcm, freeze_time, mocker
):
    # No task seeded at 14:30
    seed_data(task_hour=15, task_minute=0)
    mocker.patch("app.worker.db.build_engine", return_value=mocker.MagicMock())
    mocker.patch("app.worker.db.make_session_factory", return_value=session_factory)

    rc = worker.run()
    assert rc == 0
    mock_fcm.assert_not_called()
