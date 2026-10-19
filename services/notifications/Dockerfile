# Standalone image for the notifications service (used after extraction; see EXTRACTION_PLAYBOOK step 2).
# Inside the monorepo, build with the shared docker/Dockerfile instead (APP=...).
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app
COPY . .
RUN uv sync --frozen --no-dev --package notifications-service

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
RUN useradd --system --uid 10001 app
WORKDIR /app
COPY --from=builder /app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/readyz').status==200 else 1)"
CMD ["uvicorn", "--factory", "notifications_api.main:create_app", "--host", "0.0.0.0", "--port", "8000"]
