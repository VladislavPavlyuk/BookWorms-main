# Date Due Slip / QNAP TS-233
#
# Postgres + Nginx (+ Django API) — Container Station.
# Телефон у тій же LAN: http://192.168.0.213:18088
#
# 1. Скопіюй репо на NAS (або git clone у Shared Folder).
# 2. cp deploy/qnap/.env.example .env  (у корені репо) і зміни паролі.
# 3. Container Station → Create → docker-compose (файл docker-compose.qnap.yml)
#    або SSH:
#      docker compose -f docker-compose.qnap.yml up -d --build
# 4. Перевірка: curl http://192.168.0.213:18088/api/health/
#    ОБОВ’ЯЗКОВО має бути "code_rev":"2026-09-15-purge-v3"
#    Якщо лише {"status":"ok","app":"date-due-slip"} — на NAS СТАРИЙ код.
#
# Синхрон з ПК (приклад, підстав свій user/host):
#   rsync -av --delete \
#     --exclude .git --exclude date-due-slip --exclude .env \
#     /path/to/BookWorms-main/ admin@192.168.0.213:/share/Container/BookWorms-main/
# Потім на NAS:
#   sh deploy/qnap/rebuild-api.sh
#
# НЕ достатньо `docker compose up -d --build`, якщо файли на NAS не оновлені:
# Docker візьме CACHED COPY і ти крутитимеш старий образ.

#
# Порт 18088 (8080/443/8088 на QNAP часто зайняті).
# RAM: postgres 256M + api 384M + nginx 32M. TS-233 має 2GB — не став інші важкі контейнери поруч.
# ARM64 (RTD1296) — офіційні postgres/nginx/python образи.

QNAP TS-233 — Date Due Slip
===========================

Стек в контейнерах:
  nginx :18088  →  Django API :8000  →  Postgres 16 (внутрішня мережа)

React Native клієнт: каталог date-due-slip/
  EXPO_PUBLIC_API_URL=http://192.168.0.213:18088

Бізнес-логіка = BookWorms (полиця, ISBN, обмін/позика, пости, лайки, чат після запиту).
Додано due_date на позику (Date Due Slip), за замовчуванням 14 днів.

Пошта: Web3Forms (WEB3FORMS_ACCESS_KEY + PUBLIC_BASE_URL).
SKIP_EMAIL_ACTIVATION=0 — обов’язково для 5-хв purge непідтверджених
  (якщо =1, юзери одразу is_active=True і purge їх не чіпає).
ACTIVATION_TIMEOUT_MINUTES=5 — строк на confirm email; daemon у api (MainappConfig).
