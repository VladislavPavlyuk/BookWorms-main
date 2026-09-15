#!/bin/sh
# Запускати НА NAS у /share/Container/BookWorms-main ПІСЛЯ того, як
# свіжий код з машини розробки вже скопійовано сюди.
#
# Перевірка, що код не старий:
#   test -f bookworms/mainApp/middleware.py || { echo "STALE: sync code first"; exit 1; }
#   grep -q purged_now bookworms/api/views.py || { echo "STALE views"; exit 1; }
#
set -e
cd "$(dirname "$0")/../.."

echo "== preflight =="
test -f bookworms/mainApp/middleware.py
test -f bookworms/mainApp/migrations/0013_customuser_email_confirmed.py
grep -q purged_now bookworms/api/views.py
grep -q "purge loop" deploy/qnap/api/entrypoint.sh
grep -q code_rev bookworms/api/views.py
wc -c bookworms/api/views.py deploy/qnap/api/entrypoint.sh
ls -la bookworms/mainApp/middleware.py

export CACHEBUST="$(date +%s)"
echo "CACHEBUST=$CACHEBUST"

docker compose -f docker-compose.qnap.yml build --no-cache api
docker compose -f docker-compose.qnap.yml up -d --force-recreate api nginx

echo "== wait =="
sleep 8
echo "== health (must contain code_rev) =="
curl -sS "http://127.0.0.1:18088/api/health/" || curl -sS "http://192.168.0.213:18088/api/health/"
echo
echo "== logs (expect: entrypoint: purge pid / purge:) =="
docker compose -f docker-compose.qnap.yml logs --tail=30 api
