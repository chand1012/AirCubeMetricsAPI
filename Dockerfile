FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock README.md ./
COPY aircube_metrics_api ./aircube_metrics_api
RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 8000

CMD ["/app/.venv/bin/uvicorn", "aircube_metrics_api.api:app", "--host", "0.0.0.0", "--port", "8000"]
