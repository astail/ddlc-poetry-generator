FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml ./
COPY app ./app
COPY tests ./tests
COPY scripts ./scripts

RUN pip install --no-cache-dir ".[dev]"

# The FastAPI server is implemented in issue #6. Until then the image is used
# for unit tests:  docker compose run --rm --no-deps api python -m pytest
CMD ["sh", "-c", "echo 'API server not implemented yet (see issue #6)'; sleep infinity"]
