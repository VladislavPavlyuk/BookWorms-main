#!/bin/sh
# На NAS: /share/Container/BookWorms-main
set -e
cd "$(dirname "$0")/../.."

echo "== preflight =="
# ISBN keys must live in project-root .env (compose env_file + /app/.env mount).
# Prefer deploy/qnap/.env as the source of truth when root .env is missing keys.
if [ -f deploy/qnap/.env ]; then
  if [ ! -f .env ]; then
    cp deploy/qnap/.env .env
    echo "created .env from deploy/qnap/.env"
  elif ! grep -qE '^ISBNDB_API_KEY=.+' .env 2>/dev/null; then
    if grep -qE '^ISBNDB_API_KEY=.+' deploy/qnap/.env 2>/dev/null; then
      # merge key lines from deploy/qnap/.env into root .env
      grep -E '^(ISBNDB_API_KEY|ISBNDB_REST_KEY|GOOGLE_BOOKS_API_KEY|BOOK_METADATA_PROVIDERS|LIBRARYTHING_API_KEY)=' deploy/qnap/.env >> .env
      echo "appended ISBN keys from deploy/qnap/.env → .env"
    fi
  fi
fi
if ! grep -qE '^ISBNDB_API_KEY=.+' .env 2>/dev/null; then
  echo "FAIL: project-root .env has no ISBNDB_API_KEY" >&2
  echo "  (rsync often excludes .env — NAS never got the key.)" >&2
  echo "  Fix once on NAS, then re-run this script:" >&2
  echo "    cat >> .env <<'EOF'" >&2
  echo "    ISBNDB_API_KEY=75156_830b99831a14e268ab1fc721463c8cab" >&2
  echo "    GOOGLE_BOOKS_API_KEY=AIzaSyAVmq9S7PSeHRXbpbYKN2psT5YKBd5HxZk" >&2
  echo "    BOOK_METADATA_PROVIDERS=isbndb,openlibrary,googlebooks,librarything" >&2
  echo "    EOF" >&2
  exit 1
fi
# Guard against the compose bug that blanked the key via environment: ${ISBNDB_API_KEY:-}
if grep -qE 'ISBNDB_API_KEY: \$\{ISBNDB_API_KEY' docker-compose.qnap.yml 2>/dev/null; then
  echo "FAIL: docker-compose.qnap.yml still injects ISBNDB_API_KEY via environment: — remove it" >&2
  exit 1
fi
test -f bookworms/mainApp/middleware.py
test -f bookworms/mainApp/migrations/0018_bookcopy_shelf_copy.py
test -f bookworms/mainApp/migrations/0019_copyevent.py
test -f bookworms/mainApp/migrations/0021_copy_queue_and_transmit.py
test -f bookworms/mainApp/migrations/0022_loan_handoff.py
test -f bookworms/mainApp/migrations/0023_bookphoto.py
test -f bookworms/mainApp/migrations/0024_book_cover_text.py
test -f bookworms/mainApp/migrations/0025_book_price_evaluation.py
test -f bookworms/mainApp/migrations/0026_bookcopy_listing_status.py
test -f bookworms/mainApp/migrations/0027_bookcopy_listing_flags.py
test -f bookworms/mainApp/book_price.py
test -f bookworms/mainApp/copy_listing.py
grep -q 'class BookPriceEvaluation' bookworms/mainApp/models.py
grep -q 'is_fee_sharing' bookworms/mainApp/models.py
test -f bookworms/mainApp/static/js/isbn_scan.js
test -f bookworms/mainApp/static/js/isbn_scan_worker.js
test -f bookworms/mainApp/static/js/zxing-0.21.3.min.js
test -f bookworms/mainApp/static/js/manual_book_photos.js
test -f bookworms/mainApp/isbn_scan_assets.py
grep -q 'isbn_scan_asset' bookworms/mainApp/urls.py
grep -q 'class LoanHandoff' bookworms/mainApp/models.py
grep -q 'class BookPhoto' bookworms/mainApp/models.py
grep -q 'class AddIsbnForm' bookworms/mainApp/forms.py
grep -q 'Cheap by default' bookworms/api/views.py
grep -q 'code_rev' bookworms/api/views.py
grep -q 'post_worker_init' bookworms/bookworms/gunicorn.conf.py
# entrypoint must NOT spawn manage.py purge loop (starves workers)
if grep -q 'purge loop every' deploy/qnap/api/entrypoint.sh; then
  echo "FAIL: entrypoint still has purge loop — remove it" >&2
  exit 1
fi
wc -c bookworms/api/views.py deploy/qnap/api/entrypoint.sh

export CACHEBUST="$(date +%s)"
echo "CACHEBUST=$CACHEBUST"

docker compose -f docker-compose.qnap.yml build api
docker compose -f docker-compose.qnap.yml up -d --force-recreate api nginx

echo "== wait for health (up to 120s) =="
ok=0
i=0
while [ "$i" -lt 40 ]; do
  i=$((i + 1))
  body=$(curl -sS --max-time 3 "http://127.0.0.1:18088/api/health/" 2>/dev/null || true)
  case "$body" in
    *\"db\":\"ok\"*|*\"status\":\"ok\"*)
      echo "$body"
      ok=1
      break
      ;;
  esac
  echo "  try $i: not ready yet (${#body} bytes)"
  sleep 3
done

if [ "$ok" != 1 ]; then
  echo "FAIL: health not ok — dump:"
  docker compose -f docker-compose.qnap.yml ps
  docker compose -f docker-compose.qnap.yml logs --tail=80 api
  docker compose -f docker-compose.qnap.yml exec -T api curl -sS --max-time 3 http://127.0.0.1:8000/api/health/ || true
  exit 1
fi

echo "== migrate (post-up) =="
docker compose -f docker-compose.qnap.yml exec -T api python manage.py showmigrations mainApp | tail -20
docker compose -f docker-compose.qnap.yml exec -T api python manage.py migrate --noinput
docker compose -f docker-compose.qnap.yml exec -T api python manage.py migrate mainApp --noinput

echo "== api logs =="
docker compose -f docker-compose.qnap.yml logs --tail=60 api
echo "== ISBN env check =="
docker compose -f docker-compose.qnap.yml exec -T api python - <<'PY' || true
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bookworms.settings")
import django
django.setup()
from mainApp import isbndb as idb
from mainApp.book_lookup import fetch_book_by_isbn, _providers
print("providers", _providers())
print("isbndb_configured", idb.configured(), "key_len", len(idb.api_key()))
book, err = fetch_book_by_isbn("9789667482596")
print("lookup_9789667482596", (book or {}).get("title"), (book or {}).get("source"), err)
PY
echo "== deep health =="
curl -sS --max-time 20 "http://127.0.0.1:18088/api/health/?deep=1" | python -c '
import json,sys
d=json.load(sys.stdin)
print("code_rev", d.get("code_rev"))
print("isbndb_configured", d.get("isbndb_configured"), "ok", d.get("isbndb_ok"), "key_len", d.get("isbndb_key_len"), "err", d.get("isbndb_error"))
print("googlebooks_key_set", d.get("googlebooks_key_set"), "err", d.get("googlebooks_error"))
' || true
echo "== done =="
echo "Expect: code_rev≥2026-10-07-isbn-formdata, isbndb_ok=true, lookup title≈O druzhbe"
