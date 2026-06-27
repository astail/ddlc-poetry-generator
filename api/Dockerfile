FROM python:3.12-slim

WORKDIR /app

# Install pinned dependencies first (better layer caching + reproducible builds).
# requirements.txt is generated from pyproject.toml:
#   uv pip compile pyproject.toml --extra dev -o requirements.txt
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY alembic ./alembic
COPY tests ./tests
COPY scripts ./scripts

# Install the app package itself without re-resolving deps (already pinned above).
RUN pip install --no-cache-dir --no-deps .

# Run DB migrations separately:  docker compose run --rm api alembic upgrade head
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
