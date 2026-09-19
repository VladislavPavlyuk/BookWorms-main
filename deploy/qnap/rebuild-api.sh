#!/bin/sh
# На NAS: /share/Container/BookWorms-main
set -e
cd "$(dirname "$0")/../.."

echo "== preflight =="
test -f bookworms/mainApp/middleware.py
test -f bookworms/mainApp/migrations/0017_privatemessage_related_shelf.py
grep -q health-cheap bookworms/api/views.py
grep -q 'Cheap by default' bookworms/api/views.py
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
    *health-cheap*|*\"db\":\"ok\"*)
      echo "$body"
      ok=1
      break
      ;;
  esac
  echo "  try $i: not ready yet (${#body} bytes)"
  sleep 3
done

if [ "$ok" != 1 ]; then
  echo "FAIL: health without cheap code_rev — dump:"
  docker compose -f docker-compose.qnap.yml ps
  docker compose -f docker-compose.qnap.yml logs --tail=80 api
  docker compose -f docker-compose.qnap.yml exec -T api curl -sS --max-time 3 http://127.0.0.1:8000/api/health/ || true
  exit 1
fi

echo "== api logs =="
docker compose -f docker-compose.qnap.yml logs --tail=40 api
