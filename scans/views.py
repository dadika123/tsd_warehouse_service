import json
import queue
import threading

from django.http import HttpRequest, JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import WarehouseScan

# Подписчики SSE (открытые вкладки браузера). Каждый — своя очередь сообщений.
_subscribers = set()
_subscribers_lock = threading.Lock()


def _serialize(scan: WarehouseScan) -> dict:
    return {
        "id": scan.id,
        "solvo_data": scan.solvo_data,
        "uip": scan.uip,
        "cargo": scan.cargo,
        "pallet": scan.pallet,
        "created_at": scan.created_at.isoformat(),
    }


def _broadcast(payload: dict) -> None:
    with _subscribers_lock:
        targets = list(_subscribers)
    for target in targets:
        target.put(payload)


@require_GET
def healthz(request: HttpRequest) -> JsonResponse:
    """Проверка живости сервиса (для healthcheck контейнера и балансировщика)."""
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # noqa: BLE001
        return JsonResponse({"status": "error", "database": "down"}, status=503)
    return JsonResponse({"status": "ok", "database": "up"})


def index(request: HttpRequest):
    """Веб-страница с таблицей принятых сканов (обновляется в реальном времени)."""
    total = WarehouseScan.objects.count()
    scans = list(WarehouseScan.objects.all()[:200])
    return render(
        request, "scans/index.html", {"scans": scans, "total": total}
    )


def _field(payload: dict, name: str) -> str:
    value = payload.get(name)
    if value is None:
        return ""
    return str(value).strip()


@csrf_exempt
@require_POST
def create_scan(request: HttpRequest) -> JsonResponse:
    """Принимает JSON с четырьмя переменными и сохраняет строку в таблицу."""
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse(
            {"status": "error", "message": "Некорректный JSON"}, status=400
        )

    if not isinstance(payload, dict):
        return JsonResponse(
            {"status": "error", "message": "Ожидался JSON-объект"}, status=400
        )

    scan = WarehouseScan.objects.create(
        solvo_data=_field(payload, "solvo_data"),
        uip=_field(payload, "uip"),
        cargo=_field(payload, "cargo"),
        pallet=_field(payload, "pallet"),
    )

    # Толкаем новую строку во все открытые страницы.
    _broadcast(_serialize(scan))

    return JsonResponse({"status": "ok", "id": scan.id}, status=201)


@require_GET
def list_scans(request: HttpRequest) -> JsonResponse:
    """Последние сохранённые сканы — для проверки работы сервиса."""
    try:
        limit = int(request.GET.get("limit", "50"))
    except ValueError:
        limit = 50
    limit = max(1, min(limit, 500))

    items = [_serialize(scan) for scan in WarehouseScan.objects.all()[:limit]]
    return JsonResponse({"status": "ok", "count": len(items), "items": items})


@require_GET
def stream(request: HttpRequest) -> StreamingHttpResponse:
    """SSE-поток: присылает новые сканы по мере поступления."""

    def event_stream():
        subscriber: "queue.Queue[dict]" = queue.Queue()
        with _subscribers_lock:
            _subscribers.add(subscriber)
        try:
            # Просим браузер переподключаться через 3 с при обрыве.
            yield "retry: 3000\n\n"
            while True:
                try:
                    item = subscriber.get(timeout=15)
                except queue.Empty:
                    # Комментарий-пинг, чтобы соединение не закрывалось.
                    yield ": keep-alive\n\n"
                    continue
                data = json.dumps(item, ensure_ascii=False)
                yield f"data: {data}\n\n"
        finally:
            with _subscribers_lock:
                _subscribers.discard(subscriber)

    response = StreamingHttpResponse(
        event_stream(), content_type="text/event-stream"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
