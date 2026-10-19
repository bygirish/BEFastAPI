# syntax=docker/dockerfile:1.7
# One image for every app in the monorepo (rule E-2). Choose what to run with the build arg APP_PACKAGE
# and the container command. Multi-stage: dependencies are resolved in a throw-away builder; the runtime
# image has no build tools and runs as a non-root user.

ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.11.17

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# ----------------------------------------------------------------------------- builder
FROM python:${PYTHON_VERSION}-slim AS builder
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

ARG APP_PACKAGE=monolith-app
COPY pyproject.toml uv.lock .python-version ./
COPY libs ./libs
COPY apps ./apps
COPY services ./services
# --frozen: never touch uv.lock (reproducible). --no-dev: no test tools in the image.
# Workspace members are installed editable, so the source stays at /app (migrations live there too).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package "${APP_PACKAGE}"

# ----------------------------------------------------------------------------- runtime
FROM python:${PYTHON_VERSION}-slim AS runtime
ARG APP_VERSION=dev
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.title="befastapi" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:${PATH}" \
    APP_VERSION="${APP_VERSION}"

RUN useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
USER app

EXPOSE 8000
# /readyz = "can serve traffic" (checks every enabled service's database).
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=2).status == 200 else 1)"]

STOPSIGNAL SIGTERM
# JSON logs come from our own middleware; uvicorn's plain-text access log would duplicate them.
CMD ["uvicorn", "--factory", "monolith_app.main:create_app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
