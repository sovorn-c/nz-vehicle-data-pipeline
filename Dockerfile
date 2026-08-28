FROM python:3.12.11-slim-bookworm AS builder

# Install uv from official Astral binary
COPY --from=ghcr.io/astral-sh/uv:0.6.5 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install locked dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application files and install project
COPY README.md ./
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
COPY fixtures ./fixtures
RUN uv sync --frozen --no-dev

# Final minimal runtime image
FROM python:3.12.11-slim-bookworm

WORKDIR /app

# Run as non-root user
RUN useradd -u 10001 -m -s /bin/bash appuser

# Copy app and virtual environment from builder
COPY --from=builder --chown=appuser:appuser /app /app
COPY --from=ghcr.io/astral-sh/uv:0.6.5 /uv /bin/uv

USER appuser

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "nz_vehicle_data_pipeline.api:app", "--host", "0.0.0.0", "--port", "8000"]
