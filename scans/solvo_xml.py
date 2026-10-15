"""Формирование XML-документов Solvo по данным скана.

Поддерживаются три типа документов (структуры повторяют сообщения Solvo):

* ``order_reserve_info`` — информация о резервировании;
* ``receiving_result``   — результат приёмки;
* ``order_result``       — результат заказа.

Значения полей берутся из скана. Поля, для которых данных нет, заполняются
символом ``-`` (см. ``EMPTY``). Постоянные реквизиты сообщения (``action``,
``type``) остаются как в оригинальных документах.
"""
import xml.etree.ElementTree as ET

EMPTY = "-"

# Постоянные реквизиты сообщений.
ACTION = "update"
RECEIVING_TYPE = "S"
ORDER_TYPE = "Sc"


def _val(value) -> str:
    """Значение поля: данные скана или EMPTY, если данных нет."""
    text = "" if value is None else str(value).strip()
    return text if text else EMPTY


def _sub(parent: ET.Element, tag: str, value=None) -> ET.Element:
    element = ET.SubElement(parent, tag)
    element.text = _val(value)
    return element


def build_order_reserve_info(scan) -> ET.Element:
    """Структура order_reserve_info: marker3=solvo_data, order_id=cargo, lot=pallet."""
    root = ET.Element("order_reserve_info")
    _sub(root, "syncd")
    _sub(root, "syncdate")
    _sub(root, "order_sdid")
    _sub(root, "order_id", scan.cargo)
    _sub(root, "action", ACTION)

    detail = ET.SubElement(root, "order_reserve_detail_info")
    _sub(detail, "uip", scan.uip)
    _sub(detail, "syncd")
    _sub(detail, "syncdate")
    _sub(detail, "sku_sdid")
    _sub(detail, "reserved_units")
    _sub(detail, "prod_date")
    _sub(detail, "pick_type")
    _sub(detail, "pd_scope")
    _sub(detail, "order_sdid")
    _sub(detail, "order_id", scan.cargo)
    _sub(detail, "mvs_qid")
    _sub(detail, "marker5")
    _sub(detail, "marker3", scan.solvo_data)
    _sub(detail, "lot", scan.pallet)
    _sub(detail, "loc_tier")
    _sub(detail, "loc_name")
    _sub(detail, "load_name")
    _sub(detail, "load_id")
    _sub(detail, "action", ACTION)
    return root


def build_receiving_result(scan) -> ET.Element:
    """Структура receiving_result: marker3=solvo_data, lot=pallet, spec_tag1=article."""
    root = ET.Element("receiving_result")
    _sub(root, "unl_complete")
    _sub(root, "type", RECEIVING_TYPE)
    _sub(root, "syncd")
    _sub(root, "syncdate")
    _sub(root, "supplier_id")
    _sub(root, "rcv_date")
    _sub(root, "rcn_id")
    _sub(root, "arr_date")
    _sub(root, "action", ACTION)

    details = ET.SubElement(root, "receiving_result_details")
    detail = ET.SubElement(details, "receiving_result_detail")
    _sub(detail, "weight")
    _sub(detail, "uip", scan.uip)
    _sub(detail, "syncd")
    _sub(detail, "syncdate")
    _sub(detail, "spec_tag1", scan.product_article)
    _sub(detail, "sku_id")
    _sub(detail, "rcn_id")
    _sub(detail, "qty")
    _sub(detail, "production_date")
    _sub(detail, "marker3", scan.solvo_data)
    _sub(detail, "marker2")
    _sub(detail, "marker")
    _sub(detail, "lot", scan.pallet)
    _sub(detail, "line")
    _sub(detail, "inc_ln")
    _sub(detail, "inc_id")
    _sub(detail, "holder_id")
    _sub(detail, "expiration_date")
    _sub(detail, "comments")
    _sub(detail, "category")
    _sub(detail, "action", ACTION)
    return root


def build_order_result(scan) -> ET.Element:
    """Структура order_result: order_id/number_order=cargo, marker3=solvo_data."""
    root = ET.Element("order_result")
    _sub(root, "wms_doc_id")
    _sub(root, "type", ORDER_TYPE)
    _sub(root, "syncd")
    _sub(root, "syncdate")
    _sub(root, "spec_tag1")
    _sub(root, "order_id", scan.cargo)
    _sub(root, "number_order", scan.cargo)
    _sub(root, "pick_l")
    _sub(root, "action", ACTION)

    detail = ET.SubElement(root, "order_result_detail")
    _sub(detail, "syncd")
    _sub(detail, "syncdate")
    _sub(detail, "sku_id")
    _sub(detail, "qty")
    _sub(detail, "production_date")
    _sub(detail, "order_id", scan.cargo)
    _sub(detail, "mvs_qid")
    _sub(detail, "marker5")
    _sub(detail, "marker3", scan.solvo_data)
    _sub(detail, "marker2")
    _sub(detail, "marker")
    _sub(detail, "lot", scan.pallet)
    _sub(detail, "loc_name")
    _sub(detail, "load_status")
    _sub(detail, "line")
    _sub(detail, "category")
    _sub(detail, "action", ACTION)

    scan_load = ET.SubElement(root, "order_result_scan_load")
    _sub(scan_load, "weight")
    _sub(scan_load, "syncd")
    _sub(scan_load, "syncdate")
    _sub(scan_load, "sku_id")
    _sub(scan_load, "qty")
    _sub(scan_load, "production_date")
    _sub(scan_load, "order_id", scan.cargo)
    _sub(scan_load, "name", scan.product_name)
    _sub(scan_load, "marker5")
    _sub(scan_load, "marker2")
    _sub(scan_load, "lot", scan.pallet)
    _sub(scan_load, "loc_name")
    _sub(scan_load, "line")
    _sub(scan_load, "id")
    _sub(scan_load, "expiration_date")
    _sub(scan_load, "action", ACTION)

    pallets = ET.SubElement(root, "order_result_pallets_qty")
    _sub(pallets, "syncd")
    _sub(pallets, "syncdate")
    _sub(pallets, "pallets_qty", scan.pallet)
    _sub(pallets, "order_id", scan.cargo)
    _sub(pallets, "action", ACTION)

    sscc = ET.SubElement(root, "order_result_sscc_info")
    _sub(sscc, "syncd")
    _sub(sscc, "syncdate")
    _sub(sscc, "sscc")
    return root


# Реестр доступных типов XML-документов.
XML_BUILDERS = {
    "order_reserve_info": build_order_reserve_info,
    "receiving_result": build_receiving_result,
    "order_result": build_order_result,
}


def render_xml(root: ET.Element) -> bytes:
    """Сериализует дерево в UTF-8 XML с декларацией и отступами."""
    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"
    ).encode("utf-8")


def build_xml(scan, xml_type: str) -> bytes:
    """Собирает XML указанного типа для скана. Бросает KeyError для неизвестного типа."""
    return render_xml(XML_BUILDERS[xml_type](scan))
