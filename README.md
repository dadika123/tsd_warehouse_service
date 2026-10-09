# TSD Warehouse Service

Django-сервис для приёма складских кодов паллет (переменные GS1 94/95/96/97),
сохранения их в базу и отображения в режиме реального времени.

Сервис принимает разобранный код паллеты от приложения ТСД и складывает
поля в таблицу `scans_warehousescan`. Веб-страница показывает последние
сканы и обновляется «на лету» через SSE.

## Возможности

- Приём JSON с четырьмя переменными паллеты (`94`, `95`, `96`, `97`).
- Хранение сканов в SQLite (`db.sqlite3`).
- Веб-таблица последних сканов с обновлением в реальном времени (Server-Sent Events).
- JSON API для создания, чтения списка и подписки на поток сканов.
- Прод (Gunicorn + WhiteNoise), healthcheck, запуск в Docker Compose.

## Стек

- Python 3.12
- Django 5.2
- Gunicorn (WSGI-сервер), WhiteNoise (отдача статики)

## Быстрый старт в продакшене (Docker Compose)

1. Скопируйте пример окружения и заполните секрет:

   ```bash
   cp .env.example .env
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   # вставьте полученное значение в DJANGO_SECRET_KEY
   ```

2. Соберите и запустите:

   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```

3. Проверьте состояние:

   ```bash
   docker compose -f docker-compose.prod.yml ps
   curl http://localhost:8081/healthz/
   ```

Сервис доступен по адресу:

- **Host:** `0.0.0.0` (localhost / IP машины)
- **Порт:** `8081` (наружный, задаётся `HOST_PORT`) → `8000` (в контейнере)
- **URL:** `http://localhost:8081/`

Остановить:

```bash
docker compose -f docker-compose.prod.yml down
```

Данные SQLite сохраняются в именованном volume `warehouse_db`.

## Запуск без Compose

```bash
docker build -t tsd-warehouse-service:latest .
docker run -d --name tsd-warehouse-service --restart unless-stopped \
  --env-file .env \
  -e DJANGO_DB_PATH=/app/dbdata/db.sqlite3 \
  -v warehouse_db:/app/dbdata \
  -p 8081:8000 \
  tsd-warehouse-service:latest
```

Контейнер стартует под непривилегированным пользователем `app`, применяет
миграции и собирает статику в `entrypoint.sh`, затем запускает Gunicorn.

## Локальный запуск (разработка)

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
set DJANGO_DEBUG=true          # Windows; в *nix: export DJANGO_DEBUG=true
python manage.py migrate
python manage.py runserver 0.0.0.0:8001
```

В режиме `DJANGO_DEBUG=true` секретный ключ можно не задавать (используется
значение по умолчанию).

## API

| Метод | Путь | Описание |
|-------|------|----------|
| `GET`  | `/` | Веб-страница с таблицей последних сканов |
| `GET`  | `/healthz/` | Проверка живости сервиса и БД |
| `POST` | `/api/warehouse/` | Принять новый скан (JSON) |
| `GET`  | `/api/warehouse/list/?limit=50` | Список последних сканов |
| `GET`  | `/api/warehouse/stream/` | SSE-поток новых сканов |

### Пример создания скана

```bash
curl -X POST http://localhost:8081/api/warehouse/ \
  -H "Content-Type: application/json" \
  -d '{"solvo_data": "данные для Солво", "uip": "УИП", "cargo": "номер груза", "pallet": "номер паллеты"}'
```

Ответ:

```json
{"status": "ok", "id": 1}
```

## Конфигурация

Все настройки читаются из переменных окружения (см. `.env.example`):

| Переменная | Назначение | По умолчанию |
|------------|-----------|--------------|
| `DJANGO_SECRET_KEY` | Секретный ключ Django. **Обязателен** без DEBUG | — |
| `DJANGO_DEBUG` | Режим отладки | `False` |
| `DJANGO_ALLOWED_HOSTS` | Разрешённые Host через запятую | `*` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Доверенные origin для CSRF | пусто |
| `DJANGO_DB_PATH` | Путь к SQLite | `<project>/db.sqlite3` |
| `DJANGO_LOG_LEVEL` | Уровень логирования | `INFO` |
| `HOST_PORT` | Наружный порт в Compose | `8081` |
| `GUNICORN_WORKERS` | Число worker'ов | `1` |
| `GUNICORN_THREADS` | Потоков на worker | `8` |
| `DJANGO_SECURE_SSL_REDIRECT` | Редирект HTTP→HTTPS | `False` |
| `DJANGO_SECURE_HSTS_SECONDS` | HSTS (сек) | `0` |

### Важно про SSE и воркеры

Рассылка новых сканов хранится в памяти процесса (`scans/views.py`), поэтому
согласована только внутри одного worker'а. Конфигурация Gunicorn по умолчанию —
`1 worker × N потоков`. Не увеличивайте число worker'ов без выноса брокера
подписчиков во внешний сервис (Redis/RabbitMQ и т.п.).

## Структура проекта

```
manage.py                   точка входа Django
requirements.txt            зависимости
Dockerfile                  прод-сборка (Gunicorn, non-root)
docker-compose.prod.yml     запуск сервиса в продакшене
gunicorn.conf.py            конфигурация Gunicorn
entrypoint.sh               миграции и сбор статики перед стартом
.env.example                пример переменных окружения
warehouse_service/          настройки проекта (settings, urls, wsgi/asgi)
scans/                      приложение приёма и просмотра сканов
  models.py                 модель WarehouseScan
  views.py                  обработчики (index, healthz, create_scan, list_scans, stream)
  urls.py                   маршруты приложения
  migrations/               миграции БД
  templates/scans/          HTML-шаблоны
```

## Эксплуатация

- Резервное копирование: сохраняйте файл БД из volume `warehouse_db`
  (`docker compose -f docker-compose.prod.yml exec web ...` или `docker cp`).
- За TLS-прокси включите `DJANGO_SECURE_SSL_REDIRECT=true`,
  `DJANGO_SESSION_COOKIE_SECURE=true`, `DJANGO_CSRF_COOKIE_SECURE=true`
  и задайте `DJANGO_SECURE_HSTS_SECONDS`.
- SQLite подходит для небольшой внутренней нагрузки. При росте нагрузки
  и числа реплик перейдите на PostgreSQL и общий брокер для SSE.
