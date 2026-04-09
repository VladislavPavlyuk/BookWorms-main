import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Завантажити .env до перевірки AZURE_SQL_* (локальна розробка).
dotenv_path = BASE_DIR / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)

# Azure SQL або локальний SQLite
# На Linux потрібен установлений ODBC (див. startup.sh для App Service).
# Ім'я драйвера: odbcinst -q -d у SSH; за замовчуванням 18, можна MSSQL_ODBC_DRIVER у env.
if os.getenv("AZURE_SQL_HOST"):
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

# Azure HTTPS: https://твій-app.azurewebsites.net (через кому, якщо кілька)
_csrf = os.environ.get("CSRF_TRUSTED_ORIGINS", "").strip()
CSRF_TRUSTED_ORIGINS = [x.strip() for x in _csrf.split(",") if x.strip()]

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
    'mainApp',
    'profileApp',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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
TIME_ZONE = 'UTC'
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

# --- НАСТРОЙКИ ПОЧТЫ (GMAIL SMTP) ---
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'sandbox.smtp.mailtrap.io'
EMAIL_HOST_USER = '77163a6ec3fc20'      # Скопируй из Mailtrap
EMAIL_HOST_PASSWORD = '64fdc2428f8e99' # Скопируй из Mailtrap
EMAIL_PORT = 2525                    # Или 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False

# Этот адрес будет отображаться в поле "От кого"
DEFAULT_FROM_EMAIL = 'admin@bookworms.com'

# Тип ID моделей по умолчанию (убирает Warnings)
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

