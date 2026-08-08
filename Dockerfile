# syntax=docker/dockerfile:1.6

# ===== Stage 1: builder =====
FROM python:3.12-slim-bookworm AS builder
WORKDIR /build

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ===== Stage 2: runtime =====
FROM python:3.12-slim-bookworm

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin worker

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/*.whl \
    && rm -rf /wheels /root/.cache

COPY app/ ./app/

USER worker

# Liveness check (cheap; does not require DB)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=2 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

CMD ["python", "-m", "app.worker"]
