# Platform-owned. Built by CI, run on ECS Fargate behind the platform ALB.
FROM python:3.12-slim-bookworm AS base
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /usr/local/bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1 PYTHONUNBUFFERED=1
WORKDIR /app

FROM base AS build
COPY pyproject.toml uv.lock* README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable 2>/dev/null || uv sync --no-dev --no-editable

FROM base AS runtime
RUN useradd --system --uid 10001 --create-home app
COPY --from=build --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app fixtures ./fixtures
USER app
# The package is installed into the venv, so tell the app where the sample data lives.
ENV PATH=/app/.venv/bin:$PATH PORT=8080 APP_FIXTURES_DIR=/app/fixtures
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz').status==200 else 1)"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips=*"]
