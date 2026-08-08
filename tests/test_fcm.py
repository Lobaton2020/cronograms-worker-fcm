"""Tests for app.fcm (firebase-admin wrapper)."""

import pytest

from app import fcm


@pytest.fixture
def firebase_messages_mock(mocker):
    """Patch firebase_admin.messaging.send used inside fcm.send."""
    return mocker.patch("app.fcm.messaging.send", return_value="test-msg-id")


@pytest.fixture
def fake_admin_app(mocker):
    """Patch firebase_admin.initialize_app."""
    return mocker.patch("app.fcm.firebase_admin.initialize_app")


@pytest.fixture
def fake_cert(mocker):
    """Patch credentials.Certificate."""
    return mocker.patch("app.fcm.credentials.Certificate", return_value="fake-cert")


@pytest.fixture
def task():
    return fcm.Task(
        id=42,
        description="Hacer ejercicio",
        hour=14,
        minute=30,
        project_name="Salud",
        fcm_token="tok-abc",
    )


def test_build_message_uses_project_name_in_title(task):
    msg = fcm.build_message(task)
    assert msg.notification.title == "⏰ Salud"
    assert msg.notification.body == "14:30 - Hacer ejercicio"
    assert msg.token == "tok-abc"
    assert msg.data == {"task_id": "42"}


def test_build_message_fallback_title_when_no_project(task):
    task_no_proj = fcm.Task(
        id=1, description="x", hour=0, minute=0, project_name=None, fcm_token="t"
    )
    msg = fcm.build_message(task_no_proj)
    assert msg.notification.title == "⏰ Tarea"


def test_build_message_formats_hour_minute(task):
    task_fmt = fcm.Task(
        id=1, description="x", hour=9, minute=5, project_name="x", fcm_token="t"
    )
    msg = fcm.build_message(task_fmt)
    assert msg.notification.body == "09:05 - x"


def test_init_firebase_is_idempotent(fake_admin_app, fake_cert, mocker):
    mocker.patch.dict("os.environ", {"GOOGLE_APPLICATION_CREDENTIALS": "/path/to/sa.json"})
    fcm.reset_for_tests()
    fcm.init_firebase()
    fcm.init_firebase()  # second call should be no-op
    assert fake_admin_app.call_count == 1


def test_init_firebase_raises_without_credentials(mocker):
    mocker.patch.dict("os.environ", {}, clear=True)
    fcm.reset_for_tests()
    with pytest.raises(RuntimeError, match="GOOGLE_APPLICATION_CREDENTIALS"):
        fcm.init_firebase()


def test_init_firebase_uses_explicit_path(fake_admin_app, fake_cert, mocker):
    mocker.patch.dict("os.environ", {}, clear=True)
    fcm.reset_for_tests()
    fcm.init_firebase("/explicit/path.json")
    assert fake_cert.call_args.args[0] == "/explicit/path.json"


def test_send_initializes_firebase_if_not_yet(fake_admin_app, fake_cert, firebase_messages_mock, mocker, task):
    mocker.patch.dict("os.environ", {"GOOGLE_APPLICATION_CREDENTIALS": "/x.json"})
    fcm.reset_for_tests()
    msg_id = fcm.send(task)
    assert msg_id == "test-msg-id"
    assert fake_admin_app.call_count == 1


def test_send_returns_message_id(firebase_messages_mock, fake_admin_app, fake_cert, mocker, task):
    mocker.patch.dict("os.environ", {"GOOGLE_APPLICATION_CREDENTIALS": "/x.json"})
    fcm.reset_for_tests()
    fcm.init_firebase()
    msg_id = fcm.send(task)
    assert msg_id == "test-msg-id"
    firebase_messages_mock.assert_called_once()


def test_send_propagates_error(firebase_messages_mock, fake_admin_app, fake_cert, mocker, task):
    mocker.patch.dict("os.environ", {"GOOGLE_APPLICATION_CREDENTIALS": "/x.json"})
    fcm.reset_for_tests()
    fcm.init_firebase()
    firebase_messages_mock.side_effect = RuntimeError("FCM down")
    with pytest.raises(RuntimeError, match="FCM down"):
        fcm.send(task)
