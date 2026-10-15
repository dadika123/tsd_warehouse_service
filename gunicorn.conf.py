"""Конфигурация Gunicorn для продакшен-запуска сервиса.

Используется асинхронный gevent-воркер: долгоживущие SSE-соединения (открытые
вкладки) обслуживаются зелёными потоками (greenlets) и не занимают OS-потоки,
поэтому даже много открытых страниц не приводят к «зависанию» сервиса.

Один процесс (workers=1): рассылка новых сканов хранится в памяти процесса,
поэтому она согласована только внутри одного воркера. Не увеличивайте
workers без выноса брокера подписчиков во внешний сервис (Redis и т.п.).
"""
import os

bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")

worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "gevent")
workers = int(os.environ.get("GUNICORN_WORKERS", "1"))
worker_connections = int(os.environ.get("GUNICORN_WORKER_CONNECTIONS", "1000"))

timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", "5"))

accesslog = os.environ.get("GUNICORN_ACCESS_LOG", "-")
errorlog = os.environ.get("GUNICORN_ERROR_LOG", "-")
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

forwarded_allow_ips = os.environ.get("GUNICORN_FORWARDED_ALLOW_IPS", "*")
