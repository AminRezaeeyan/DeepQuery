#!/bin/sh
# Waits for PostgreSQL, then (for the API only) migrates and collects static files.
set -e

python - <<'PY'
import os, time
import psycopg

for attempt in range(60):
    try:
        psycopg.connect(
            host=os.environ.get("DB_HOST", "localhost"), port=os.environ.get("DB_PORT", "5432"),
            dbname=os.environ.get("DB_NAME", "deepquery"), user=os.environ.get("DB_USER", "deepquery_user"),
            password=os.environ.get("DB_PASSWORD", ""), connect_timeout=3,
        ).close()
        break
    except psycopg.OperationalError:
        time.sleep(2)
else:
    raise SystemExit("PostgreSQL did not become ready.")
PY

if [ "$1" = "gunicorn" ]; then
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput
fi

exec "$@"
