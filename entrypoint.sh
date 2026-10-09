#!/bin/sh
set -e

# Применяем миграции и собираем статику перед стартом приложения.
python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
