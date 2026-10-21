"""
Ежедневная очистка отгрузок.

- через 180 дней после завершения (finished_at) статус → «Удалено»;
- через 240 дней запись и её файл удаляются из БД.
"""

from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from scans.models import Shipment


class Command(BaseCommand):
    help = "Помечает старые отгрузки удалёнными и удаляет совсем старые"

    def add_arguments(self, parser):
        parser.add_argument(
            "--as-of",
            help="Дата проверки в формате YYYY-MM-DD (для тестов)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать, что будет сделано",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        as_of = options.get("as_of")
        if as_of:
            try:
                parsed = datetime.strptime(as_of, "%Y-%m-%d").date()
            except ValueError as exc:
                raise CommandError("--as-of должен быть в формате YYYY-MM-DD") from exc
            now = timezone.make_aware(datetime.combine(parsed, time.min))

        delete_cutoff = now - timedelta(days=240)
        mark_cutoff = now - timedelta(days=180)

        to_delete = Shipment.objects.filter(finished_at__lte=delete_cutoff)
        to_mark = (
            Shipment.objects.filter(
                finished_at__lte=mark_cutoff,
                finished_at__gt=delete_cutoff,
            )
            .exclude(status=Shipment.STATUS_DELETED)
        )

        delete_count = to_delete.count()
        mark_count = to_mark.count()

        if options.get("dry_run"):
            self.stdout.write(
                f"Будет помечено удалёнными: {mark_count}, "
                f"удалено из БД: {delete_count}."
            )
            return

        deleted_files = 0
        for shipment in to_delete:
            if shipment.file:
                try:
                    shipment.file.delete(save=False)
                    deleted_files += 1
                except Exception:
                    pass
            shipment.delete()

        marked = to_mark.update(status=Shipment.STATUS_DELETED)

        self.stdout.write(
            self.style.SUCCESS(
                f"Помечено удалёнными: {marked}, удалено из БД: {delete_count} "
                f"(файлов: {deleted_files})."
            )
        )
