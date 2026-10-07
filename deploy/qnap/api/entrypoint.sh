#!/bin/sh
set -e

# Compose often freezes stale/empty ISBNDB_API_KEY from an older .env into the
# container environment. Re-export ISBN secrets from the bind-mounted /app/.env
# so lookups (e.g. 9789667482596 on ISBNdb) actually see the live key.
if [ -f /app/.env ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      \#*|"") continue ;;
      ISBNDB_API_KEY=*|ISBNDB_REST_KEY=*|GOOGLE_BOOKS_API_KEY=*|LIBRARYTHING_API_KEY=*|BOOK_METADATA_PROVIDERS=*)
        key=${line%%=*}
        val=${line#*=}
        # strip inline comments and surrounding whitespace
        val=${val%%#*}
        val=$(printf '%s' "$val" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        case "$val" in
          ""|your_rest_key|your-rest-key|changeme|xxx|TODO|todo) continue ;;
        esac
        export "$key=$val"
        ;;
    esac
  done < /app/.env
  echo "entrypoint: ISBN env from /app/.env ISBNDB_len=${#ISBNDB_API_KEY} providers=${BOOK_METADATA_PROVIDERS:-}" >&2
else
  echo "entrypoint: WARNING /app/.env missing — ISBN keys may be empty" >&2
fi

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
echo "entrypoint: ISBN provider smoke..." >&2
python - <<'PY' || echo "entrypoint: ISBN smoke failed (non-fatal)" >&2
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bookworms.settings")
import django
django.setup()
from mainApp import isbndb as idb
from mainApp.book_lookup import _providers

print(
    f"entrypoint: providers={_providers()} isbndb_configured={idb.configured()} key_len={len(idb.api_key())}",
    flush=True,
)
if idb.configured():
    book, err = idb.fetch_book_by_isbn("9789667482596")
    title = (book or {}).get("title") if book else None
    print(f"entrypoint: isbndb smoke 9789667482596 title={title!r} err={err!r}", flush=True)
else:
    print("entrypoint: ISBNDB_API_KEY missing — ISBN add will fail for books only on ISBNdb", flush=True)
PY

echo "entrypoint: starting gunicorn..." >&2
exec gunicorn bookworms.wsgi:application \
  --config bookworms/gunicorn.conf.py \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-1}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
