#!/bin/sh
# Live-DB repository tests on QNAP (bridge + links). Do not exec into dds-api.
set -e
cd "$(dirname "$0")/../.."

TARGET="${1:-django}"
# Bust Docker COPY layers — QNAP often rebuilds from stale cache.
export CACHEBUST="${CACHEBUST:-$(date +%s)}"

docker compose -f docker-compose.test.yml up -d postgres

case "$TARGET" in
  django)
    docker compose -f docker-compose.test.yml run --rm --build django-test
    ;;
  fastapi)
    docker compose -f docker-compose.test.yml run --rm --build fastapi-test
    ;;
  all)
    docker compose -f docker-compose.test.yml run --rm --build django-test
    docker compose -f docker-compose.test.yml run --rm --build fastapi-test
    ;;
  *)
    echo "usage: $0 [django|fastapi|all]" >&2
    exit 2
    ;;
esac
