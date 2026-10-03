#!/bin/sh
# Container start: migrate, then serve.
set -e
alembic upgrade head
exec uvicorn osfl.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
