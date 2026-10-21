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

    # Данные справочника продукции (UIP), подтягиваются по GTIN из УИП.
    gtin = models.CharField(max_length=14, blank=True, verbose_name="GTIN")
    product_name = models.CharField(
        max_length=512, blank=True, verbose_name="Наименование продукта"
    )
    product_article = models.CharField(
        max_length=128, blank=True, verbose_name="Артикул"
    )
    product_id = models.CharField(
        max_length=64, blank=True, verbose_name="ID продукта"
    )

    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, verbose_name="Создан"
    )

    class Meta:
        verbose_name = "Скан паллеты"
        verbose_name_plural = "Сканы паллет"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.pallet or '-'} ({self.uip or '-'})"


class Shipment(models.Model):
    """Отгрузка: уникальный код, дата, артикул и файл агрегации (XML/JSON)."""

    FORMAT_JSON = "json"
    FORMAT_XML = "xml"
    FORMAT_CHOICES = [
        (FORMAT_JSON, "JSON"),
        (FORMAT_XML, "XML"),
    ]

    STATUS_CREATED = "created"
    STATUS_IN_WORK = "in_work"
    STATUS_CLOSED = "closed"
    STATUS_COMPLETED = "completed"
    STATUS_DELETED = "deleted"
    STATUS_CHOICES = [
        (STATUS_CREATED, "Создано"),
        (STATUS_IN_WORK, "В работе"),
        (STATUS_CLOSED, "Закрыто"),
        (STATUS_COMPLETED, "Завершено"),
        (STATUS_DELETED, "Удалено"),
    ]

    shipment_id = models.CharField(
        max_length=64, unique=True, verbose_name="Идентификатор отгрузки"
    )
    shipment_date = models.CharField(
        max_length=10, verbose_name="Дата отгрузки"
    )
    article = models.CharField(
        max_length=128, verbose_name="Артикул товара"
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_CREATED,
        db_index=True,
        verbose_name="Статус",
    )
    file_format = models.CharField(
        max_length=8, choices=FORMAT_CHOICES, blank=True, default="",
        verbose_name="Формат файла",
    )
    file = models.FileField(
        upload_to="shipments/", blank=True, default="", verbose_name="Файл агрегации"
    )
    # Данные для формирования файла в выбранном формате уже в сервисе.
    aggregations = models.JSONField(
        default=list, blank=True, verbose_name="Агрегации"
    )
    packages_count = models.PositiveIntegerField(
        default=0, verbose_name="Упаковок"
    )
    children_count = models.PositiveIntegerField(
        default=0, verbose_name="Дочерних кодов"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, verbose_name="Создано"
    )
    finished_at = models.DateTimeField(
        null=True, blank=True, db_index=True, verbose_name="Завершено"
    )

    class Meta:
        verbose_name = "Отгрузка"
        verbose_name_plural = "Отгрузки"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.shipment_id} ({self.article})"
