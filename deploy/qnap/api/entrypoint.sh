#!/bin/sh
set -e
echo "entrypoint: wait postgres..." >&2
python - <<'PY'
import os, socket, time, sys
host = os.environ.get("POSTGRES_HOST", "postgres")
port = int(os.environ.get("POSTGRES_PORT", "5432"))
for _ in range(60):
    try:
        s = socket.create_connection((host, port), 2)
        s.close()
        print("entrypoint: postgres ok", flush=True)
        sys.exit(0)
    except OSError:
        time.sleep(1)
print("postgres not reachable", file=sys.stderr)
sys.exit(1)
PY

echo "entrypoint: migrate..." >&2
python manage.py migrate --noinput
echo "entrypoint: collectstatic..." >&2
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
if [ "${PURGE_UNACTIVATED:-1}" = "1" ] || [ "${PURGE_UNACTIVATED:-1}" = "true" ]; then
  # nohup + background: переживає exec gunicorn (shell → gunicorn same PID)
  nohup sh -c "
    echo entrypoint: purge loop every ${PURGE_INTERVAL}s >&2
    while true; do
      python manage.py purge_unactivated || echo purge_cmd_failed >&2
      sleep ${PURGE_INTERVAL}
    done
  " >/proc/1/fd/1 2>/proc/1/fd/2 &
  echo "entrypoint: purge spawned pid $!" >&2
fi

echo "entrypoint: starting gunicorn..." >&2
exec gunicorn bookworms.wsgi:application \
  --config bookworms/gunicorn.conf.py \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-1}" \
  --threads "${GUNICORN_THREADS:-2}" \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
