#!/bin/sh
set -e
python - <<'PY'
import os, socket, time, sys
host = os.environ.get("POSTGRES_HOST", "postgres")
port = int(os.environ.get("POSTGRES_PORT", "5432"))
for _ in range(60):
    try:
        s = socket.create_connection((host, port), 2)
        s.close()
        sys.exit(0)
    except OSError:
        time.sleep(1)
print("postgres not reachable", file=sys.stderr)
sys.exit(1)
PY

python manage.py migrate --noinput
python manage.py collectstatic --noinput

if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ]; then
  python - <<'PY'
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bookworms.settings")
import django
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
u = os.environ["DJANGO_SUPERUSER_USERNAME"]
if not User.objects.filter(username=u).exists():
    User.objects.create_superuser(
        username=u,
        email=os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@local"),
        password=os.environ["DJANGO_SUPERUSER_PASSWORD"],
    )
    print("superuser created", flush=True)
else:
    print("superuser exists", flush=True)
PY
fi

PURGE_INTERVAL="${PURGE_UNACTIVATED_INTERVAL:-30}"
PURGE_PID=""
GUNI_PID=""

term() {
  echo "entrypoint: shutting down..."
  [ -n "$GUNI_PID" ] && kill -TERM "$GUNI_PID" 2>/dev/null || true
  [ -n "$PURGE_PID" ] && kill -TERM "$PURGE_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  exit 0
}
trap term TERM INT

# Окремий процес purge — shell лишається PID1 і тримає обидва.
if [ "${PURGE_UNACTIVATED:-1}" = "1" ] || [ "${PURGE_UNACTIVATED:-1}" = "true" ]; then
  (
    echo "entrypoint: purge loop every ${PURGE_INTERVAL}s" >&2
    while true; do
      python manage.py purge_unactivated || echo "purge command failed" >&2
      sleep "${PURGE_INTERVAL}"
    done
  ) &
  PURGE_PID=$!
  echo "entrypoint: purge pid ${PURGE_PID}" >&2
fi

gunicorn bookworms.wsgi:application \
  --config bookworms/gunicorn.conf.py \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-1}" \
  --threads "${GUNICORN_THREADS:-2}" \
  --timeout 60 \
  --access-logfile - \
  --error-logfile - &
GUNI_PID=$!
echo "entrypoint: gunicorn pid ${GUNI_PID}" >&2

wait "$GUNI_PID"
term
