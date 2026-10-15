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
]
