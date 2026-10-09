from django.contrib import admin

from .models import WarehouseScan


@admin.register(WarehouseScan)
class WarehouseScanAdmin(admin.ModelAdmin):
    list_display = ("id", "pallet", "cargo", "uip", "created_at")
    search_fields = ("pallet", "cargo", "uip")
