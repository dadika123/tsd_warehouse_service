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

## Стек

- Python 3.12
- Django 5.2 (см. `requirements.txt`)

## Запуск через Docker (рекомендуется)

Сборка образа:

```bash
docker build -t tsd-warehouse-service:latest .
```

Запуск контейнера:

```bash
docker run -d --name tsd-warehouse-service --restart unless-stopped -p 8081:8000 tsd-warehouse-service:latest
```

Сервис будет доступен по адресу:

- **Host:** `0.0.0.0` (localhost / IP машины)
- **Порт:** `8081` (наружный) → `8000` (в контейнере)
- **URL:** `http://localhost:8081/`

Остановить / удалить:

```bash
docker stop tsd-warehouse-service
docker rm tsd-warehouse-service
```

## Локальный запуск (без Docker)

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8001
```

Сервис будет доступен по адресу `http://localhost:8001/`.

## API

| Метод | Путь | Описание |
|-------|------|----------|
| `GET`  | `/` | Веб-страница с таблицей последних сканов |
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

## Структура проекта

```
manage.py                  точка входа Django
requirements.txt           зависимости
Dockerfile                 сборка контейнера
warehouse_service/         настройки проекта (settings, urls, wsgi/asgi)
scans/                     приложение приёма и просмотра сканов
  models.py                модель WarehouseScan
  views.py                 обработчики (index, create_scan, list_scans, stream)
  urls.py                  маршруты приложения
  migrations/              миграции БД
  templates/scans/         HTML-шаблоны
```

## Конфигурация

Основные настройки — в `warehouse_service/settings.py`:

- `DEBUG = True`, `ALLOWED_HOSTS = ["*"]` — сервис рассчитан на локальную сеть.
- База данных — SQLite (`db.sqlite3`, создаётся миграциями).
- Часовой пояс — `Europe/Moscow`.

> Внимание: используется встроенный сервер разработки Django. Для
> промышленной эксплуатации подключите WSGI/ASGI-сервер (gunicorn, uvicorn и т.п.).
