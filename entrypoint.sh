#!/bin/sh
set -e

echo "Waiting for PostgreSQL..."
while ! nc -z $POSTGRES_SERVER $POSTGRES_PORT; do
  sleep 0.5
done
echo "PostgreSQL is ready!"

echo "Running database migrations..."
alembic upgrade head || echo "Migration warning/skipped"

echo "Starting Uvicorn server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
