"""Внешние интеграции: справочник продукции (UIP) по GTIN."""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

# Ограничения совпадают с полями модели WarehouseScan.
NAME_MAX = 512
ARTICLE_MAX = 128
PRODUCT_ID_MAX = 64


def gtin_from_uip(uip: str) -> str:
    """GTIN потребительской упаковки — первые 14 символов УИП."""
    return (uip or "").strip()[:14]


def fetch_product_by_gtin(gtin: str) -> dict:
    """Запрашивает карточку продукта по GTIN.

    Возвращает словарь ответа API или пустой словарь, если товар не найден
    либо сервис недоступен. Ошибки не пробрасываются: скан сохраняется даже
    при недоступном справочнике.
    """
    gtin = (gtin or "").strip()
    if not gtin:
        return {}

    url = f"{settings.UIP_API_BASE_URL}?{urllib.parse.urlencode({'gtin': gtin})}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})

    try:
        with urllib.request.urlopen(
            request, timeout=settings.UIP_API_TIMEOUT
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            logger.info("Продукт по GTIN %s не найден", gtin)
        else:
            logger.warning("UIP API вернул HTTP %s для GTIN %s", exc.code, gtin)
        return {}
    except (urllib.error.URLError, ValueError, OSError) as exc:
        logger.warning("Не удалось получить продукт по GTIN %s: %s", gtin, exc)
        return {}

    if not isinstance(payload, dict) or payload.get("is_error"):
        return {}
    return payload


def product_fields_from_uip(uip: str) -> dict:
    """Значения полей скана с данными продукта, полученными по GTIN из УИП."""
    gtin = gtin_from_uip(uip)
    product = fetch_product_by_gtin(gtin)
    return {
        "gtin": gtin,
        "product_name": str(product.get("name") or "")[:NAME_MAX],
        "product_article": str(product.get("article") or "")[:ARTICLE_MAX],
        "product_id": str(product.get("product_id") or "")[:PRODUCT_ID_MAX],
    }
