#!/bin/sh
set -e
echo "fastapi entrypoint: wait postgres..." >&2
python - <<'PY'
import os, socket, time, sys
host = os.environ.get("POSTGRES_HOST", "postgres")
port = int(os.environ.get("POSTGRES_PORT", "5432"))
for _ in range(60):
    try:
        s = socket.create_connection((host, port), 2)
        s.close()
        print("fastapi: postgres ok", flush=True)
        sys.exit(0)
    except OSError:
        time.sleep(1)
print("postgres not reachable", file=sys.stderr)
sys.exit(1)
PY

if [ "${RUN_ALEMBIC:-1}" = "1" ]; then
  echo "fastapi entrypoint: alembic upgrade..." >&2
  (cd /app/fastapi_app && alembic upgrade head) || {
    echo "fastapi: alembic failed (ok if table exists / Django DB empty)" >&2
  }
fi

echo "fastapi entrypoint: uvicorn..." >&2
exec uvicorn fastapi_app.main:app --host 0.0.0.0 --port 8001 --workers 1
