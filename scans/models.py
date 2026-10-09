from django.db import models


class WarehouseScan(models.Model):
    """Одна отсканированная паллета, разобранная на четыре переменные GS1."""

    solvo_data = models.TextField(
        blank=True, verbose_name="94 Данные для Солво"
    )
    uip = models.CharField(
        max_length=64, blank=True, verbose_name="95 УИП"
    )
    cargo = models.CharField(
        max_length=64, blank=True, verbose_name="96 Номер груза"
    )
    pallet = models.CharField(
        max_length=64, blank=True, verbose_name="97 Номер паллеты"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    class Meta:
        verbose_name = "Скан паллеты"
        verbose_name_plural = "Сканы паллет"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.pallet or '-'} ({self.uip or '-'})"
