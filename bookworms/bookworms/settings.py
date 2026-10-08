import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
# Host repo root when running from source; inside Docker image BASE_DIR is /app.
REPO_ROOT = BASE_DIR.parent

# Compose often injects OCR_SPACE_API_KEY="" via ${VAR:-} — that blocks dotenv.
# Treat blank secrets as unset so a mounted/loaded .env can fill them.
_ISBN_PLACEHOLDERS = frozenset(
    {
        "your_rest_key",
        "your-rest-key",
        "changeme",
        "change-me",
        "xxx",
        "todo",
    }
)


def _scrub_bad_secret(name: str) -> None:
    """Drop blank/placeholder so a mounted .env can supply the real value."""
    raw = (os.environ.get(name) or "").strip()
    if "#" in raw:
        raw = raw.split("#", 1)[0].strip()
    if not raw or raw.lower() in _ISBN_PLACEHOLDERS:
        os.environ.pop(name, None)


for _blank_key in (
    "OCR_SPACE_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "ISBNDB_API_KEY",
    "ISBNDB_REST_KEY",
    "GOOGLE_BOOKS_API_KEY",
):
    _scrub_bad_secret(_blank_key)

# Load .env from every plausible location (local + Docker mount /app/.env).
# /app/.env is bind-mounted from host ./.env — must override stale compose env
# (e.g. old ISBNDB_API_KEY=your_rest_key baked into the container).
for dotenv_path in (
    BASE_DIR / ".env",
    REPO_ROOT / ".env",
    Path.cwd() / ".env",
):
    if dotenv_path.is_file():
        load_dotenv(dotenv_path, override=False)
_app_env = Path("/app/.env")
if _app_env.is_file():
    load_dotenv(_app_env, override=True)
    # re-scrub in case the mounted file still has a placeholder
    for _k in ("ISBNDB_API_KEY", "ISBNDB_REST_KEY", "GOOGLE_BOOKS_API_KEY"):
        _scrub_bad_secret(_k)

# Термін позики для Date Due Slip (днів від прийняття запиту).
DEFAULT_LOAN_DAYS = int(os.environ.get("DEFAULT_LOAN_DAYS", "14"))
# LAN/QNAP: реєстрація без SMTP (is_active=True одразу).
SKIP_EMAIL_ACTIVATION = os.environ.get("SKIP_EMAIL_ACTIVATION", "").lower() in (
    "1",
    "true",
    "yes",
)
# Неактивований акаунт видаляється, якщо email не підтверджено за N хвилин.
ACTIVATION_TIMEOUT_MINUTES = int(os.environ.get("ACTIVATION_TIMEOUT_MINUTES", "5"))

# Postgres (QNAP) → Azure SQL → SQLite
# На Linux потрібен установлений ODBC (див. startup.sh для App Service).
# Ім'я драйвера: odbcinst -q -d у SSH; за замовчуванням 18, можна MSSQL_ODBC_DRIVER у env.
if os.getenv("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "bookworms"),
            "USER": os.environ.get("POSTGRES_USER", "bookworms"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ["POSTGRES_HOST"],
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        },
    }
elif os.getenv("AZURE_SQL_HOST"):
    _odbc_driver = os.environ.get(
        "MSSQL_ODBC_DRIVER", "ODBC Driver 18 for SQL Server"
    )
    _odbc_extra = os.environ.get(
        "MSSQL_ODBC_EXTRA",
        "Encrypt=yes;TrustServerCertificate=no;",
    )
    DATABASES = {
        "default": {
            "ENGINE": "mssql",
            "NAME": os.environ["AZURE_SQL_NAME"],
            "USER": os.environ["AZURE_SQL_USER"],
            "PASSWORD": os.environ["AZURE_SQL_PASSWORD"],
            "HOST": os.environ["AZURE_SQL_HOST"],
            "PORT": "1433",
            "OPTIONS": {
                "driver": _odbc_driver,
                "extra_params": _odbc_extra,
            },
        },
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        },
    }

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-6t+ptzf#8htvjij$vg7rjl!5$)t%k#m^(gna$uvc&!l^-0&5bx",
)

# На Azure: DEBUG=False у Application settings
DEBUG = os.environ.get("DEBUG", "True").lower() in ("1", "true", "yes")

_allowed = os.environ.get("ALLOWED_HOSTS", "").strip()
if _allowed:
    ALLOWED_HOSTS = [h.strip() for h in _allowed.split(",") if h.strip()]
else:
    ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# Azure: у App Settings часто кладуть лише hostname — Django 4+ вимагає scheme (https://...).
_csrf = os.environ.get("CSRF_TRUSTED_ORIGINS", "").strip()
CSRF_TRUSTED_ORIGINS = []
for _o in (_x.strip() for _x in _csrf.split(",") if _x.strip()):
    CSRF_TRUSTED_ORIGINS.append(
        _o if "://" in _o else f"https://{_o}"
    )

# За nginx (Host / scheme з X-Forwarded-*).
USE_X_FORWARDED_HOST = os.environ.get("USE_X_FORWARDED_HOST", "1").lower() in (
    "1",
    "true",
    "yes",
)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Твои приложения
    'bookworms',
    'mainApp.apps.MainappConfig',
    'profileApp',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'mainApp.middleware.PurgeUnactivatedMiddleware',
    'mainApp.middleware.ClientAnalyticsMiddleware',
]

ROOT_URLCONF = 'bookworms.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # Рекомендую добавить общую папку шаблонов
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'mainApp.context_processors.notifications',
                'mainApp.context_processors.reader_age_scale',
                'mainApp.context_processors.book_search_languages',
                'mainApp.context_processors.book_search_subjects',
            ],
        },
    },
]

WSGI_APPLICATION = 'bookworms.wsgi.application'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'ru-ru'  # Сменил на русский для удобства админки
TIME_ZONE = os.environ.get("TIME_ZONE", "Europe/Kyiv")
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
_static_project = BASE_DIR / "static"
STATICFILES_DIRS = [_static_project] if _static_project.is_dir() else []
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Auth settings
AUTH_USER_MODEL = 'mainApp.CustomUser'
LOGOUT_REDIRECT_URL = '/'
LOGIN_REDIRECT_URL = '/'
LOGIN_URL = 'login'

# --- Пошта: Web3Forms (замість Mailtrap/SMTP) ---
# Лист іде на email, прив’язаний до access_key у кабінеті web3forms.com.
# Увага: compose часто сетить WEB3FORMS_ACCESS_KEY="" — os.environ.get тоді
# НЕ падає на default (порожній рядок ≠ відсутній ключ).
_WEB3FORMS_DEFAULT_KEY = "d76edac5-49fd-4574-b89b-45e24170aeab"
WEB3FORMS_ACCESS_KEY = (
    os.environ.get("WEB3FORMS_ACCESS_KEY") or _WEB3FORMS_DEFAULT_KEY
).strip()
# Публічний origin для лінка активації (NAS): http://192.168.0.213:18088
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@bookworms.local")

# Cover OCR (manual add) — read once so views/services share the same source.
OCR_SPACE_API_KEY = (os.environ.get("OCR_SPACE_API_KEY") or "").strip() or "K89147673988957"
OPENAI_API_KEY = (os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY") or "").strip()

# Тип ID моделей по умолчанию (убирает Warnings)
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "EXCEPTION_HANDLER": "mainApp.error_handling.drf_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=int(os.environ.get("JWT_ACCESS_DAYS", "7"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.environ.get("JWT_REFRESH_DAYS", "30"))),
    "ROTATE_REFRESH_TOKENS": False,
}

# React Native (LAN). За замовчуванням дозволити все в локальній мережі.
_cors = os.environ.get("CORS_ALLOWED_ORIGINS", "").strip()
if _cors:
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors.split(",") if o.strip()]
    CORS_ALLOW_ALL_ORIGINS = False
else:
    CORS_ALLOW_ALL_ORIGINS = True

CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "origin",
    "user-agent",
    "x-requested-with",
]

# Логи handoff/позик → stderr (docker logs dds-api)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "mainApp.ops": {
            "handlers": ["console"],
            "level": os.environ.get("OPS_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "mainApp.exchange_service": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

