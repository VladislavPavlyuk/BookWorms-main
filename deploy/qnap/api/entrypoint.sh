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

echo "entrypoint: sync avatar collection..." >&2
python manage.py sync_avatar_collection || echo "entrypoint: sync_avatar_collection failed (non-fatal)" >&2

if [ -n "${OCR_SPACE_API_KEY:-}" ]; then
  echo "entrypoint: OCR_SPACE_API_KEY=set" >&2
else
  echo "entrypoint: OCR_SPACE_API_KEY=MISSING — add to project-root .env and recreate api" >&2
fi
echo "entrypoint: collectstatic..." >&2
# Named volume staticfiles persists across rebuilds — force-refresh ISBN scanner assets
# so nginx never keeps a frozen/broken previous isbn_scan.js.
rm -f \
  /app/staticfiles/js/isbn_scan.js \
  /app/staticfiles/js/isbn_scan.js.gz \
  /app/staticfiles/js/isbn_scan_worker.js \
  /app/staticfiles/js/isbn_scan_worker.js.gz \
  /app/staticfiles/js/zxing-0.21.3.min.js \
  /app/staticfiles/js/zxing-0.21.3.min.js.gz \
  /app/staticfiles/js/script.js \
  /app/staticfiles/js/script.js.gz \
  /app/staticfiles/js/manual_book_photos.js \
  /app/staticfiles/js/manual_book_photos.js.gz \
  /app/staticfiles/css/style.css \
  /app/staticfiles/css/style.css.gz \
  2>/dev/null || true
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

# Purge крутить лише gunicorn worker thread (post_worker_init) —
# окремий manage.py loop їв DB + друкував «thread started» кожні 30s.
echo "entrypoint: starting gunicorn..." >&2
exec gunicorn bookworms.wsgi:application \
  --config bookworms/gunicorn.conf.py \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-1}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
