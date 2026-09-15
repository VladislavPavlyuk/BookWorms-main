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
    print("superuser created")
else:
    print("superuser exists")
PY
fi

exec gunicorn bookworms.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-1}" \
  --threads "${GUNICORN_THREADS:-2}" \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
