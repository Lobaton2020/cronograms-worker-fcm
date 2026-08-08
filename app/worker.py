"""CronJob entrypoint: query pending tasks, send FCM, mark as notified."""

import logging
import sys
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError

from . import db, fcm
from .config import load_config
from .timezone import current_date_bogota, current_hour_minute_bogota

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("fcm-worker")


def run() -> int:
    """Execute one cycle. Returns 0 on success, non-zero on fatal error."""
    config = load_config()
    logger.info("Starting fcm-worker cycle")

    engine = db.build_engine(config.database_url)
    SessionLocal = db.make_session_factory(engine)

    today = current_date_bogota(config.timezone)
    hour, minute = current_hour_minute_bogota(config.timezone)
    logger.info("Looking for tasks at %s %02d:%02d", today, hour, minute)

    try:
        fcm.init_firebase(config.google_application_credentials)
    except Exception:
        logger.exception("Failed to initialize Firebase")
        return 1

    sent = 0
    failed = 0
    with SessionLocal() as session:
        try:
            tasks = db.get_pending_tasks(session, today, hour, minute)
        except SQLAlchemyError:
            logger.exception("DB query failed")
            return 2

        logger.info("Found %d candidate task(s)", len(tasks))

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for row in tasks:
            task = fcm.Task(
                id=row.id,
                description=row.description,
                hour=row.hour,
                minute=row.minute,
                project_name=row.project_name,
                fcm_token=row.fcm_token,
            )
            try:
                msg_id = fcm.send(task)
                db.mark_notified(session, task.id, now)
                logger.info("task %d notified (msg=%s)", task.id, msg_id)
                sent += 1
            except Exception as exc:
                logger.exception("Failed to send task %d: %s", task.id, exc)
                failed += 1

    logger.info("Cycle finished: sent=%d failed=%d", sent, failed)
    return 0 if failed == 0 else 0


def main() -> int:
    try:
        return run()
    except Exception:
        logger.exception("Unhandled fatal error")
        return 99


if __name__ == "__main__":
    sys.exit(main())
