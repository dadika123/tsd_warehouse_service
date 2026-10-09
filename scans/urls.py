from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/warehouse/", views.create_scan, name="create_scan"),
    path("api/warehouse/list/", views.list_scans, name="list_scans"),
    path("api/warehouse/stream/", views.stream, name="warehouse_stream"),
]
