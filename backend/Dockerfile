FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
RUN uv pip install --system -e .

COPY . .

# Pick the runtime by START_COMMAND. Workers skip migrations; the API runs
# `alembic upgrade head` first so schema changes apply on every deploy.
# Railway honours this Dockerfile CMD on the Luka API service even when
# railway.toml specifies releaseCommand/startCommand, which is why migrations
# stopped running silently when those values diverged.
CMD ["sh", "-c", "case \"$START_COMMAND\" in worker-fast) exec python -m arq worker.FastWorkerSettings;; worker-slow) exec python -m arq worker.SlowWorkerSettings;; *) alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000};; esac"]
