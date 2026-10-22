from django.urls import path

from . import views

urlpatterns = [
    path("healthz/", views.healthz, name="healthz"),
    path("", views.index, name="index"),
    path("api/warehouse/", views.create_scan, name="create_scan"),
    path("api/warehouse/list/", views.list_scans, name="list_scans"),
    path(
        "api/warehouse/<int:scan_id>/xml/<str:xml_type>/",
        views.scan_xml,
        name="scan_xml",
    ),
    path("api/warehouse/stream/", views.stream, name="warehouse_stream"),
    # Отгрузки: отдельная вкладка и API для ТСД.
    path("shipments/", views.shipments, name="shipments"),
    path(
        "shipments/<int:shipment_id>/generate/",
        views.generate_shipment_file,
        name="generate_shipment_file",
    ),
    path(
        "shipments/<int:shipment_id>/send-1c/",
        views.send_shipment_to_1c,
        name="send_shipment_to_1c",
    ),
    path("api/shipments/", views.create_shipment, name="create_shipment"),
    path("api/shipments/list/", views.list_shipments, name="list_shipments"),
    path(
        "api/v1/shipments/<str:shipment_id>/codes/",
        views.shipment_consumer_codes,
        name="shipment_consumer_codes",
    ),
    # Старый неверсионированный путь — для совместимости.
    path(
        "api/shipments/<str:shipment_id>/codes/",
        views.shipment_consumer_codes,
        name="shipment_consumer_codes_legacy",
    ),
    path(
        "api/shipments/stream/",
        views.shipment_stream,
        name="shipment_stream",
    ),
]
