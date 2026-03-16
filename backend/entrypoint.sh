#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting Seabay API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --access-log
