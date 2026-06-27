FROM python:3.14-slim

# Run as a non-root user (defence in depth, #55). The named /data volume inherits
# this ownership on first init so the app and workers can write generated assets.
RUN useradd --create-home --uid 10001 app

WORKDIR /app

# Install pinned RUNTIME deps only — no dev tools (pytest/ruff) or tests in the
# production image (smaller image, smaller attack surface). Regenerate with:
#   uv pip compile pyproject.toml -o requirements.txt
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY alembic ./alembic

# Install the app package without re-resolving deps (already pinned above), then
# hand ownership of the workdir + data mountpoint to the non-root user.
RUN pip install --no-cache-dir --no-deps . \
    && mkdir -p /data \
    && chown -R app:app /app /data

USER app

# Migrations run via the one-shot `migrate` service:  docker compose run --rm migrate
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
