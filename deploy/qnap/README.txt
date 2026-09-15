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
# 5. Admin: http://192.168.0.213:18088/admin/
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
SKIP_EMAIL_ACTIVATION=1 — реєстрація без листа (зручно для LAN).
