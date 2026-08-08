-- 001_add_notified_at.sql
-- Adds the notified_at column to tarea_cronograma.
-- The worker uses this column to mark tasks as already notified
-- (idempotent anti-duplicate logic).

ALTER TABLE tarea_cronograma
    ADD COLUMN notified_at DATETIME NULL;

ALTER TABLE tarea_cronograma
    ADD INDEX idx_notified_at (notified_at);
