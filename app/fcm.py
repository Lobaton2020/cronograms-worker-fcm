"""Firebase Cloud Messaging wrapper.

Initializes the firebase-admin SDK exactly once and exposes a single
`send()` function used by the worker.
"""

import logging
import os
from dataclasses import dataclass

import firebase_admin
from firebase_admin import credentials, messaging

logger = logging.getLogger(__name__)

_initialized = False


def init_firebase(credentials_path: str | None = None) -> None:
    """Initialize the firebase-admin app. Idempotent."""
    global _initialized
    if _initialized:
        return

    path = credentials_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not path:
        raise RuntimeError(
            "GOOGLE_APPLICATION_CREDENTIALS is not set and no credentials_path given"
        )

    cred = credentials.Certificate(path)
    firebase_admin.initialize_app(cred)
    _initialized = True
    logger.info("Firebase Admin SDK initialized")


def reset_for_tests() -> None:
    """Reset internal state. For tests only."""
    global _initialized
    _initialized = False


@dataclass(frozen=True)
class Task:
    id: int
    description: str
    hour: int
    minute: int
    project_name: str | None
    fcm_token: str


def build_message(task: Task) -> messaging.Message:
    """Build the FCM message for a task. Pure function for easy testing."""
    title = f"⏰ {task.project_name or 'Tarea'}"
    body = f"{task.hour:02d}:{task.minute:02d} - {task.description}"
    return messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data={"task_id": str(task.id)},
        token=task.fcm_token,
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                channel_id="task_alarm",
                sound="default",
            ),
        ),
    )


def send(task: Task) -> str:
    """Send an FCM push for the given task. Returns the FCM message id."""
    if not _initialized:
        init_firebase()
    message = build_message(task)
    return messaging.send(message)
