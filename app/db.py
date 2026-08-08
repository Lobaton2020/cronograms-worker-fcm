"""Database access layer using SQLAlchemy 2.0 Core (no ORM)."""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


def build_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine with sensible defaults for a short-lived job."""
    return create_engine(
        database_url,
        pool_size=2,
        pool_pre_ping=True,
        pool_recycle=300,
        future=True,
    )


def make_session_factory(engine: Engine):
    """Return a sessionmaker bound to the engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


PENDING_TASKS_SQL = text(
    """
    SELECT
        tc.id_tarea_cronograma_PK AS id,
        tc.descripcion        AS description,
        tc.hora               AS hour,
        tc.minuto             AS minute,
        p.name                AS project_name,
        ft.token              AS fcm_token
    FROM tarea_cronograma tc
    INNER JOIN cronograma c
        ON tc.id_cronograma_FK = c.id_cronograma_PK
    INNER JOIN fcm_tokens ft
        ON ft.id_usuario_FK = c.id_usuario_FK
    LEFT JOIN projects p
        ON tc.project_id = p.id
    WHERE tc.estado = 0
      AND tc.notified_at IS NULL
      AND DATE(c.fecha) = :today
      AND tc.hora = :hour
      AND tc.minuto = :minute
    """
)


MARK_NOTIFIED_SQL = text(
    """
    UPDATE tarea_cronograma
    SET notified_at = :now
    WHERE id_tarea_cronograma_PK = :id
      AND notified_at IS NULL
    """
)


def get_pending_tasks(session, today, hour: int, minute: int) -> list:
    """Return tasks scheduled for the given date/hour/minute that need notification."""
    return list(
        session.execute(
            PENDING_TASKS_SQL,
            {"today": today, "hour": hour, "minute": minute},
        )
    )


def mark_notified(session, task_id: int, now) -> int:
    """Mark a task as notified. Returns rowcount (0 if already notified)."""
    result = session.execute(MARK_NOTIFIED_SQL, {"id": task_id, "now": now})
    session.commit()
    return result.rowcount
