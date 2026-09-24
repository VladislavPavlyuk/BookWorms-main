# Date Due Slip (BookWorms)

Обмін / позика фізичних книг з **терміном повернення** (Date Due Slip), стрічкою постів і чатом після запиту.

Прод на QNAP TS-233: **http://192.168.0.213:18088** (TLS — на edge / reverse proxy).

---

## Що всередині

| Частина | Шлях | Роль |
|--------|------|------|
| Django + DRF | `bookworms/` | Web UI, admin, JWT auth, exchange writes, основний `/api/` |
| FastAPI strangler | `fastapi_app/` | Паралельний процес: JWT (SimpleJWT-compatible) + shelf read APIs |
| Expo / RN клієнт | `date-due-slip/` | Android / iOS / macOS → той самий API |
| QNAP deploy | `deploy/qnap/`, `docker-compose.qnap.yml` | postgres + api + fastapi + nginx |

**Домен обміну** (`bookworms/mainApp/exchange/`): copies, shelves, requests, handoff, returns, queue; порти / сервіси / репозиторії.  
**Меседжинг** (`bookworms/mainApp/messaging/`): partners, handoff panel, thread context.  
Помилки обміну: `ExchangeError*` + DRF `EXCEPTION_HANDLER`.

---

## Архітектура (runtime)

```text
Clients (RN / browser)
        │  HTTPS (edge TLS)
        ▼
   dds-nginx :18088
        ├── /api/*, / …     → dds-api (Django :8000)
        └── /fastapi/…      → dds-fastapi (:8001)
                │
                ▼
         dds-postgres (shared)
```

- `Authorization: Bearer <access>` прокидається nginx → Python.
- Django SimpleJWT і FastAPI PyJWT ділять **`DJANGO_SECRET_KEY`** (HS256, `token_type` / `user_id`).
- Схема `mainApp_*` — **тільки Django migrations**. Alembic у FastAPI лише `fastapi_*`.

---

## Стек

- **Python 3.12**, Django, DRF, SimpleJWT, Gunicorn  
- **FastAPI**, SQLAlchemy Core, Pydantic, PyJWT, passlib (Django PBKDF2)  
- **Postgres 16**, Nginx  
- **Expo** (SecureStore для access/refresh)

---

## Швидкий старт (QNAP)

```bash
cd /share/Container/BookWorms-main
cp deploy/qnap/.env.example .env   # паролі, SECRET, PUBLIC_BASE_URL
docker compose -f docker-compose.qnap.yml up -d --build
```

Перевірка:

```bash
curl -s http://192.168.0.213:18088/api/health/
curl -s http://192.168.0.213:18088/fastapi/health
```

| Порт / шлях | Сервіс |
|-------------|--------|
| `:18088` | nginx → Django + `/fastapi/` |
| `:18089` | FastAPI напряму (debug) |
| `/api/…` | Django DRF |
| `/fastapi/auth/*`, `/fastapi/v1/shelves/*` | FastAPI |
| `/fastapi/docs` | OpenAPI FastAPI |

Синк з дев-машини (приклад):

```bash
rsync -av --delete \
  --exclude .git --exclude date-due-slip --exclude .env \
  /path/to/BookWorms-main/ admin@192.168.0.213:/share/Container/BookWorms-main/
sh deploy/qnap/rebuild-api.sh   # або compose up --build; див. CACHEBUST
```

Деталі QNAP / bridge+links / RAM: [`deploy/qnap/README.txt`](deploy/qnap/README.txt).

---

## Auth

**Клієнт (primary):** Django

- `POST /api/auth/register/` — з Web3Forms activation, якщо `SKIP_EMAIL_ACTIVATION=0`
- `POST /api/auth/login/`, `POST /api/auth/refresh/`
- RN: `date-due-slip/src/api.ts` → SecureStore + Bearer

**FastAPI (strangler):**

- `POST /fastapi/auth/login`, `/refresh`
- `POST /fastapi/auth/register` — лише при `SKIP_EMAIL_ACTIVATION=1` (інакше 400 → Django register)
- Shelf: обов’язковий Bearer; `viewer_id` з токена

`SKIP_EMAIL_ACTIVATION=0` + `ACTIVATION_TIMEOUT_MINUTES` — purge непідтверджених акаунтів.

---

## Основний API (Django)

Префікс `/api/` — полиця, ISBN lookup, browse, exchanges, handoff, returns, queue, posts, likes, comments, messages, notifications. Повний список: `bookworms/api/urls.py`.

---

## FastAPI slice

Докладніше: [`fastapi_app/README.md`](fastapi_app/README.md).

- `GET /fastapi/health`
- `GET /fastapi/v1/shelves/available-owned`
- `GET /fastapi/v1/shelves/physical-presence`

---

## Тести (жива БД)

Конвенція: `test_<method>_<when>_<returns>`, змінні `actualResult` / `expectedResult`, один assert. Repo-layer — live DB; вище — мок репозиторію.

```bash
# на NAS (docker0 + links; не exec у dds-api з 172.17.0.1)
sh deploy/qnap/run-repo-tests.sh django
sh deploy/qnap/run-repo-tests.sh fastapi
# або: sh deploy/qnap/run-repo-tests.sh all
```

Compose: `docker-compose.test.yml` (`dds-postgres-test` + one-shot runners).

---

## Локально (без NAS)

Django (з кореня `bookworms/`, після `pip install -r requirements-nas.txt` або аналог):

```bash
cd bookworms
# без POSTGRES_HOST → SQLite
python manage.py migrate
python manage.py runserver
```

FastAPI:

```bash
pip install -r requirements-fastapi.txt
# ті самі POSTGRES_* / DJANGO_SECRET_KEY що й Django
uvicorn fastapi_app.main:app --reload --port 8001
```

RN: `date-due-slip/`, `EXPO_PUBLIC_API_URL` / SecureStore API base → `http://<host>:18088`.

---

## Важливі env

Див. [`deploy/qnap/.env.example`](deploy/qnap/.env.example):

- `POSTGRES_*`, `DJANGO_SECRET_KEY`
- `PUBLIC_BASE_URL`, `SKIP_EMAIL_ACTIVATION`, `ACTIVATION_TIMEOUT_MINUTES`
- `WEB3FORMS_ACCESS_KEY`, `DEFAULT_LOAN_DAYS`
- ISBN: `BOOK_METADATA_PROVIDERS`, `ISBNDB_API_KEY`, …

FastAPI у compose отримує ті самі `DJANGO_SECRET_KEY` / JWT / `SKIP_EMAIL_ACTIVATION`.
