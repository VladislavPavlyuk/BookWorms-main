# Date Due Slip / QNAP TS-233
#
# Postgres + Nginx + Django API + FastAPI strangler — Container Station.
# Телефон у тій же LAN: http://192.168.0.213:18088
# TLS — на QNAP Reverse Proxy / Cloudflare (dds-nginx лишається :80).
#
# 1. Скопіюй репо на NAS (або git clone у Shared Folder).
# 2. cp deploy/qnap/.env.example .env  (у корені репо) і зміни паролі.
# 3. Container Station → Create → docker-compose (файл docker-compose.qnap.yml)
#    або SSH:
#      docker compose -f docker-compose.qnap.yml up -d --build
# 4. Перевірка:
#      curl -s http://192.168.0.213:18088/api/health/
#      curl -s http://192.168.0.213:18088/fastapi/health
#    У health Django шукай актуальний code_rev. Старий JSON без code_rev =
#    на NAS не синкнувся код (Docker CACHED COPY).
#
# Синхрон з ПК (приклад):
#   rsync -av --delete \
#     --exclude .git --exclude date-due-slip --exclude .env \
#     /path/to/BookWorms-main/ admin@192.168.0.213:/share/Container/BookWorms-main/
# Потім на NAS:
#   sh deploy/qnap/rebuild-api.sh
#   # або: CACHEBUST=$(date +%s) docker compose -f docker-compose.qnap.yml up -d --build
#
# Repo tests (окрема Postgres, bridge+links — НЕ 172.17.0.1 з dds-api):
#   sh deploy/qnap/run-repo-tests.sh django
#   sh deploy/qnap/run-repo-tests.sh fastapi
#
# НЕ достатньо `docker compose up -d --build`, якщо файли на NAS не оновлені.
#
# Порти: 18088 nginx, 18089 fastapi direct.
# RAM: postgres 256M + api 384M + fastapi 128M + nginx 32M.
# ARM64 (RTD1296) — офіційні postgres/nginx/python образи.
# network_mode: bridge + links (без user-defined bridge — QNET dnsmasq).

QNAP TS-233 — Date Due Slip
===========================

Стек:
  nginx :18088
    → Django API :8000   (/api, web)
    → FastAPI    :8001   (/fastapi/… — JWT + shelf reads)
  Postgres 16 (спільна БД; міграції Django)

React Native: date-due-slip/
  API base → http://192.168.0.213:18088
  JWT у SecureStore; primary auth = Django /api/auth/*

Бізнес-логіка = BookWorms (полиця, ISBN, обмін/позика, handoff, queue,
пости, вподобайки, чат після запиту). due_date на позику (DEFAULT_LOAN_DAYS=14).

Пошта: Web3Forms (WEB3FORMS_ACCESS_KEY + PUBLIC_BASE_URL).
SKIP_EMAIL_ACTIVATION=0 — для purge непідтверджених.
ACTIVATION_TIMEOUT_MINUTES=5.

Кореневий README: ../../README.md
FastAPI: ../../fastapi_app/README.md
