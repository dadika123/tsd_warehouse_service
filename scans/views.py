import json
import queue
import re
import threading
import xml.etree.ElementTree as ET

from django.core.files.base import ContentFile
from pathlib import Path

from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    JsonResponse,
    StreamingHttpResponse,
)
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import Shipment, WarehouseScan
from .services import product_fields_from_uip
from .solvo_xml import XML_BUILDERS, build_xml

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
        "gtin": scan.gtin,
        "product_name": scan.product_name,
        "product_article": scan.product_article,
        "product_id": scan.product_id,
        "created_at": scan.created_at.isoformat(),
    }


def _broadcast(payload: dict) -> None:
    with _subscribers_lock:
        targets = list(_subscribers)
    for target in targets:
        target.put(payload)


# Подписчики SSE вкладки «Отгрузки».
_shipment_subscribers = set()
_shipment_subscribers_lock = threading.Lock()


def _broadcast_shipments() -> None:
    with _shipment_subscribers_lock:
        targets = list(_shipment_subscribers)
    for target in targets:
        target.put({"type": "shipments_changed"})


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
        request,
        "scans/index.html",
        {"scans": scans, "total": total, "xml_types": list(XML_BUILDERS)},
    )


def _field(payload: dict, name: str) -> str:
    value = payload.get(name)
    if value is None:
        return ""
    return str(value).strip()


# Разрешённые переходы статусов: поздний запрос не должен откатывать статус назад.
_STATUS_TRANSITIONS = {
    Shipment.STATUS_CREATED: {
        Shipment.STATUS_CREATED,
        Shipment.STATUS_IN_WORK,
        Shipment.STATUS_CLOSED,
        Shipment.STATUS_ERROR,
    },
    Shipment.STATUS_IN_WORK: {
        Shipment.STATUS_IN_WORK,
        Shipment.STATUS_CLOSED,
        Shipment.STATUS_ERROR,
    },
    Shipment.STATUS_CLOSED: {
        Shipment.STATUS_CLOSED,
        Shipment.STATUS_COMPLETED,
        Shipment.STATUS_DELETED,
    },
    Shipment.STATUS_COMPLETED: {
        Shipment.STATUS_COMPLETED,
        Shipment.STATUS_DELETED,
    },
    Shipment.STATUS_ERROR: {
        Shipment.STATUS_ERROR,
        Shipment.STATUS_DELETED,
    },
    Shipment.STATUS_DELETED: {
        Shipment.STATUS_DELETED,
    },
}


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

    uip = _field(payload, "uip")

    # Подтягиваем данные продукта из справочника UIP по GTIN из УИП.
    scan = WarehouseScan.objects.create(
        solvo_data=_field(payload, "solvo_data"),
        uip=uip,
        cargo=_field(payload, "cargo"),
        pallet=_field(payload, "pallet"),
        **product_fields_from_uip(uip),
    )

    # Толкаем новую строку во все открытые страницы.
    _broadcast(_serialize(scan))

    return JsonResponse({"status": "ok", "id": scan.id}, status=201)


@require_GET
def scan_xml(request: HttpRequest, scan_id: int, xml_type: str) -> HttpResponse:
    """Отдаёт XML-документ Solvo указанного типа по данным скана."""
    if xml_type not in XML_BUILDERS:
        raise Http404("Неизвестный тип XML")

    scan = WarehouseScan.objects.filter(pk=scan_id).first()
    if scan is None:
        raise Http404("Скан не найден")

    content = build_xml(scan, xml_type)
    response = HttpResponse(content, content_type="application/xml; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="{xml_type}_{scan_id}.xml"'
    )
    return response


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


@require_GET
def shipment_stream(request: HttpRequest) -> StreamingHttpResponse:
    """SSE для вкладки «Отгрузки»: сообщает об изменении статусов."""

    def event_stream():
        subscriber: "queue.Queue[dict]" = queue.Queue()
        with _shipment_subscribers_lock:
            _shipment_subscribers.add(subscriber)
        try:
            yield "retry: 3000\n\n"
            while True:
                try:
                    item = subscriber.get(timeout=15)
                except queue.Empty:
                    yield ": keep-alive\n\n"
                    continue
                data = json.dumps(item, ensure_ascii=False)
                yield f"data: {data}\n\n"
        finally:
            with _shipment_subscribers_lock:
                _shipment_subscribers.discard(subscriber)

    response = StreamingHttpResponse(
        event_stream(), content_type="text/event-stream"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


# --- Отгрузки -------------------------------------------------------------

def _normalize_aggregations(raw) -> list[dict]:
    """Оставляет только валидные пары «код упаковки -> дочерние коды»."""
    if not isinstance(raw, list):
        return []

    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        parent_code = str(item.get("parentCode") or "").strip()
        children_raw = item.get("childCodes") or []
        if not isinstance(children_raw, (list, tuple)):
            continue
        child_codes = [
            str(child).strip() for child in children_raw if str(child).strip()
        ]
        if parent_code and child_codes:
            result.append({
                "parentCode": parent_code,
                "childCodes": child_codes,
            })
    return result


def _build_shipment_json(
    shipment_id: str,
    shipment_date: str,
    article: str,
    aggregations: list[dict],
) -> bytes:
    data = {
        "shipmentId": shipment_id,
        "shipmentDate": shipment_date,
        "article": article,
        "aggregations": aggregations,
    }
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


def _build_shipment_xml(
    shipment_id: str,
    shipment_date: str,
    article: str,
    aggregations: list[dict],
) -> bytes:
    root = ET.Element("shipment", {
        "id": shipment_id,
        "date": shipment_date,
        "article": article,
    })
    for aggregation in aggregations:
        parent = ET.SubElement(root, "aggregation", {
            "code": aggregation["parentCode"],
        })
        for child in aggregation["childCodes"]:
            ET.SubElement(parent, "child").text = child
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _consumer_codes(aggregations: list[dict]) -> list[str]:
    """Потребительские коды отгрузки: дочерние, не являющиеся агрегациями."""
    parents = {str(item["parentCode"]) for item in aggregations}
    codes: list[str] = []
    for item in aggregations:
        for child in item.get("childCodes", []):
            code = str(child).strip()
            if code and code not in parents and code not in codes:
                codes.append(code)
    return codes


def _build_shipment_txt(aggregations: list[dict]) -> bytes:
    """TXT-выгрузка: только потребительские коды, по одному в строке."""
    codes = _consumer_codes(aggregations)
    return ("\n".join(codes) + ("\n" if codes else "")).encode("utf-8")


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned or "shipment"


def _serialize_shipment(shipment: Shipment) -> dict:
    return {
        "id": shipment.id,
        "shipment_id": shipment.shipment_id,
        "shipment_date": shipment.shipment_date,
        "article": shipment.article,
        "status": shipment.status,
        "status_display": shipment.get_status_display(),
        "has_aggregations": bool(shipment.aggregations),
        "can_download": (
            shipment.status in (Shipment.STATUS_CLOSED, Shipment.STATUS_COMPLETED)
            and bool(shipment.aggregations or shipment.file)
        ),
        "can_send_1c": shipment.status == Shipment.STATUS_CLOSED,
        "file_format": shipment.file_format,
        "file_url": shipment.file.url if shipment.file else "",
        "packages_count": shipment.packages_count,
        "children_count": shipment.children_count,
        "created_at": shipment.created_at.isoformat(),
        "finished_at": (
            shipment.finished_at.isoformat() if shipment.finished_at else None
        ),
    }


def shipments(request: HttpRequest):
    """Отдельная вкладка со списком отгрузок и ссылками на файлы."""
    items = list(Shipment.objects.all()[:200])
    return render(
        request,
        "scans/shipments.html",
        {"shipments": items, "total": Shipment.objects.count()},
    )


@require_GET
def list_shipments(request: HttpRequest) -> JsonResponse:
    """Последние отгрузки — для проверки работы сервиса."""
    try:
        limit = int(request.GET.get("limit", "50"))
    except ValueError:
        limit = 50
    limit = max(1, min(limit, 500))

    items = [_serialize_shipment(shipment) for shipment in Shipment.objects.all()[:limit]]
    return JsonResponse({"status": "ok", "count": len(items), "items": items})


@csrf_exempt
@require_POST
def create_shipment(request: HttpRequest) -> JsonResponse:
    """
    Принимает отгрузку от ТСД:
      {shipmentId, shipmentDate, article,
       aggregations: [{parentCode, childCodes: [...]}, ...]}
    Сохраняет запись и данные агрегации. Файл формируется позже на вкладке
    «Отгрузки» в выбранном там формате (JSON/XML/TXT).
    """
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

    shipment_id = _field(payload, "shipmentId")
    previous_shipment_id = _field(payload, "previousShipmentId")
    shipment_date = _field(payload, "shipmentDate")
    article = _field(payload, "article")
    requested_status = _field(payload, "status") or Shipment.STATUS_CREATED
    has_aggregations = "aggregations" in payload
    aggregations = _normalize_aggregations(payload.get("aggregations"))

    if not shipment_id:
        return JsonResponse(
            {"status": "error", "message": "Не указан shipmentId"}, status=400
        )
    if requested_status not in dict(Shipment.STATUS_CHOICES):
        return JsonResponse(
            {"status": "error", "message": "Неизвестный статус"}, status=400
        )

    existing = Shipment.objects.filter(shipment_id=shipment_id).first()
    if (
        existing is None
        and previous_shipment_id
        and previous_shipment_id != shipment_id
    ):
        # Первый скан: заменяем placeholder-идентификатор на реальный артикул.
        existing = Shipment.objects.filter(
            shipment_id=previous_shipment_id
        ).first()
        if existing is not None:
            existing.shipment_id = shipment_id

    if existing is not None:
        current_status = existing.status
        allowed = _STATUS_TRANSITIONS.get(current_status, {current_status})
        new_status = (
            requested_status if requested_status in allowed else current_status
        )

        if shipment_date:
            existing.shipment_date = shipment_date
        if article:
            existing.article = article
        if has_aggregations and aggregations:
            existing.aggregations = aggregations
            existing.packages_count = len(aggregations)
            existing.children_count = sum(
                len(item["childCodes"]) for item in aggregations
            )
        existing.status = new_status
        if (
            new_status in (
                Shipment.STATUS_CLOSED,
                Shipment.STATUS_COMPLETED,
                Shipment.STATUS_ERROR,
            )
            and existing.finished_at is None
        ):
            existing.finished_at = timezone.now()
        existing.save()
        _broadcast_shipments()

        return JsonResponse(
            {
                "status": "ok",
                "id": existing.id,
                "fileUrl": (
                    request.build_absolute_uri(existing.file.url)
                    if existing.file else None
                ),
                "fileFormat": existing.file_format,
                "shipmentStatus": existing.status,
                "shipmentStatusDisplay": existing.get_status_display(),
                "finishedAt": (
                    existing.finished_at.isoformat()
                    if existing.finished_at else None
                ),
                "updated": True,
            },
            status=200,
        )

    if not shipment_date:
        return JsonResponse(
            {"status": "error", "message": "Не указана shipmentDate"}, status=400
        )
    if not article:
        return JsonResponse(
            {"status": "error", "message": "Не указан article"}, status=400
        )
    if requested_status == Shipment.STATUS_CLOSED and not aggregations:
        return JsonResponse(
            {"status": "error", "message": "Нет ни одной агрегации с дочерними кодами"},
            status=400,
        )

    finished_at = None
    if requested_status in (
        Shipment.STATUS_CLOSED,
        Shipment.STATUS_COMPLETED,
        Shipment.STATUS_ERROR,
    ):
        finished_at = timezone.now()

    shipment = Shipment(
        shipment_id=shipment_id,
        shipment_date=shipment_date,
        article=article,
        status=requested_status,
        aggregations=aggregations,
        packages_count=len(aggregations),
        children_count=sum(len(item["childCodes"]) for item in aggregations),
        finished_at=finished_at,
    )
    shipment.save()
    _broadcast_shipments()

    return JsonResponse(
        {
            "status": "ok",
            "id": shipment.id,
            "fileUrl": None,
            "fileFormat": "",
            "shipmentStatus": shipment.status,
            "shipmentStatusDisplay": shipment.get_status_display(),
            "finishedAt": (
                shipment.finished_at.isoformat() if shipment.finished_at else None
            ),
            "message": "Файл будет сформирован на вкладке «Отгрузки».",
        },
        status=201,
    )


@csrf_exempt
@require_POST
def generate_shipment_file(request: HttpRequest, shipment_id: int):
    """Формирует файл отгрузки в выбранном в сервисе формате (JSON/XML/TXT)."""
    file_format = (request.POST.get("file_format") or "").lower()
    if file_format not in (
        Shipment.FORMAT_JSON,
        Shipment.FORMAT_XML,
        Shipment.FORMAT_TXT,
    ):
        return HttpResponse("Формат должен быть json, xml или txt", status=400)

    shipment = Shipment.objects.filter(pk=shipment_id).first()
    if shipment is None:
        raise Http404("Отгрузка не найдена")

    aggregations = _normalize_aggregations(shipment.aggregations)
    if not aggregations:
        return HttpResponse("Нет данных агрегации для формирования файла", status=400)

    if file_format == Shipment.FORMAT_XML:
        content = _build_shipment_xml(
            shipment.shipment_id,
            shipment.shipment_date,
            shipment.article,
            aggregations,
        )
    elif file_format == Shipment.FORMAT_TXT:
        content = _build_shipment_txt(aggregations)
    else:
        content = _build_shipment_json(
            shipment.shipment_id,
            shipment.shipment_date,
            shipment.article,
            aggregations,
        )

    # Перегенерация: убираем старый файл, чтобы не копить форматы.
    if shipment.file:
        shipment.file.delete(save=False)

    filename = f"{_safe_filename(shipment.shipment_id)}.{file_format}"
    shipment.file.save(filename, ContentFile(content), save=False)
    shipment.file_format = file_format
    shipment.save(update_fields=["file", "file_format"])

    # Кнопка «Скачать» сразу отдаёт сформированный файл выбранного формата.
    return FileResponse(
        shipment.file.open("rb"),
        as_attachment=True,
        filename=Path(shipment.file.name).name,
    )


@csrf_exempt
@require_POST
def send_shipment_to_1c(request: HttpRequest, shipment_id: int):
    """Кнопка «Отправить в 1С»: пока просто переводит статус в «Завершено»."""
    shipment = Shipment.objects.filter(pk=shipment_id).first()
    if shipment is None:
        raise Http404("Отгрузка не найдена")

    if shipment.status == Shipment.STATUS_CLOSED:
        shipment.status = Shipment.STATUS_COMPLETED
        shipment.save(update_fields=["status"])
        _broadcast_shipments()

    return redirect("shipments")
