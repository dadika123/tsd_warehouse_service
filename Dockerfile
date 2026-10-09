FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_DEBUG=False

WORKDIR /app

# Непривилегированный пользователь и каталог для данных (SQLite).
RUN addgroup --system app \
    && adduser --system --ingroup app app \
    && mkdir -p /app/staticfiles /app/dbdata \
    && chown -R app:app /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=4).status == 200 else 1)"

ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "warehouse_service.wsgi:application", "-c", "gunicorn.conf.py"]
