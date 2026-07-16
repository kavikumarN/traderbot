# syntax=docker/dockerfile:1

# ---- builder: resolve and install dependencies into a venv -----------------
FROM python:3.13-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml ./
# A minimal package stub so `pip install .` can resolve metadata before the
# real source is copied in — keeps the dependency layer cacheable.
RUN mkdir app && touch app/__init__.py
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

# ---- runtime: slim image, non-root, only what's needed to run --------------
FROM python:3.13-slim AS runtime

# Traceability only — never read at runtime, just visible via `docker
# inspect` / `kubectl describe pod` to tell which commit a running
# container was built from.
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.revision=$GIT_SHA

RUN groupadd --system app && useradd --system --gid app --home-dir /app --create-home app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --chown=app:app app ./app
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini ./

USER app
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
