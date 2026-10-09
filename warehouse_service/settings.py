"""
Настройки Django-сервиса приёма складских кодов.

Сервис принимает разобранный код паллеты (переменные 94/95/96/97)
и складывает их в таблицу scans_warehousescan.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Служебный ключ для внутреннего сервиса в локальной сети.
SECRET_KEY = "django-insecure-tsd-warehouse-service-local"

# Сервис слушает локальную сеть, поэтому разрешаем любой Host.
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "scans",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "warehouse_service.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

WSGI_APPLICATION = "warehouse_service.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
