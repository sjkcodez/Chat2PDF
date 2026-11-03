#!/usr/bin/env bash
# Run the app under gunicorn locally.
#   ./scripts/run.sh
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
exec gunicorn \
  -k gthread \
  --workers 1 \
  --threads 8 \
  --bind 127.0.0.1:5000 \
  --access-logfile - \
  --error-logfile - \
  wsgi:app
