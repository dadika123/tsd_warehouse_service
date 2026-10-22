import shutil
import tempfile

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .models import Shipment
from .views import _build_shipment_txt


class ShipmentTxtBuilderTests(SimpleTestCase):
    def test_only_consumer_codes(self):
        aggregations = [
            {"parentCode": "BOX-1", "childCodes": ["U1", "U2", "U2"]},
            {"parentCode": "BOX-2", "childCodes": ["U2", "U3"]},
        ]

        self.assertEqual(_build_shipment_txt(aggregations), b"U1\nU2\nU3\n")

    def test_excludes_nested_aggregation_codes(self):
        aggregations = [
            {"parentCode": "PALLET", "childCodes": ["BOX-1", "BOX-2"]},
            {"parentCode": "BOX-1", "childCodes": ["U1", "U2"]},
            {"parentCode": "BOX-2", "childCodes": ["U3"]},
        ]

        self.assertEqual(_build_shipment_txt(aggregations), b"U1\nU2\nU3\n")

    def test_empty_aggregations(self):
        self.assertEqual(_build_shipment_txt([]), b"")


class ShipmentTxtViewTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.shipment = Shipment.objects.create(
            shipment_id="13541261021001",
            shipment_date="21.10.2026",
            article="13541",
            status=Shipment.STATUS_CLOSED,
            aggregations=[
                {"parentCode": "BOX-1", "childCodes": ["U1", "U2"]},
                {"parentCode": "BOX-2", "childCodes": ["U3"]},
            ],
            packages_count=2,
            children_count=3,
        )

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_generate_txt(self):
        response = self.client.post(
            reverse("generate_shipment_file", args=[self.shipment.id]),
            {"file_format": "txt"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"U1\nU2\nU3\n")
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.file_format, Shipment.FORMAT_TXT)
        self.assertTrue(self.shipment.file.name.endswith(".txt"))

    def test_rejects_unknown_format(self):
        response = self.client.post(
            reverse("generate_shipment_file", args=[self.shipment.id]),
            {"file_format": "csv"},
        )

        self.assertEqual(response.status_code, 400)


class ShipmentConsumerCodesApiTests(TestCase):
    def setUp(self):
        self.shipment = Shipment.objects.create(
            shipment_id="13541261021020",
            shipment_date="21.10.2026",
            article="13541",
            status=Shipment.STATUS_CLOSED,
            aggregations=[
                {"parentCode": "BOX-1", "childCodes": ["U1", "U2", "U2"]},
                {"parentCode": "BOX-2", "childCodes": ["U2", "U3"]},
            ],
        )

    def test_returns_only_consumer_codes(self):
        response = self.client.get(
            reverse("shipment_consumer_codes", args=[self.shipment.shipment_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ["U1", "U2", "U3"])

    def test_legacy_url_still_returns_codes(self):
        response = self.client.get(
            reverse(
                "shipment_consumer_codes_legacy",
                args=[self.shipment.shipment_id],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ["U1", "U2", "U3"])

    def test_excludes_nested_aggregation_codes(self):
        shipment = Shipment.objects.create(
            shipment_id="PALLET-1",
            shipment_date="21.10.2026",
            article="13500",
            status=Shipment.STATUS_CLOSED,
            aggregations=[
                {"parentCode": "PALLET", "childCodes": ["BOX-1", "BOX-2"]},
                {"parentCode": "BOX-1", "childCodes": ["U1", "U2"]},
                {"parentCode": "BOX-2", "childCodes": ["U3"]},
            ],
        )

        response = self.client.get(
            reverse("shipment_consumer_codes", args=[shipment.shipment_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ["U1", "U2", "U3"])

    def test_unknown_shipment_returns_404(self):
        response = self.client.get(
            reverse("shipment_consumer_codes", args=["UNKNOWN"])
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), [])

    def test_shipment_without_aggregations_returns_empty_list(self):
        shipment = Shipment.objects.create(
            shipment_id="EMPTY-1",
            shipment_date="21.10.2026",
            article="13541",
            status=Shipment.STATUS_CREATED,
            aggregations=[],
        )

        response = self.client.get(
            reverse("shipment_consumer_codes", args=[shipment.shipment_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])



class ShipmentFilterTests(TestCase):
    def setUp(self):
        Shipment.objects.create(
            shipment_id="F-1",
            shipment_date="20.10.2026",
            article="13541",
            status=Shipment.STATUS_CLOSED,
        )
        Shipment.objects.create(
            shipment_id="F-2",
            shipment_date="21.10.2026",
            article="13500",
            status=Shipment.STATUS_IN_WORK,
        )
        Shipment.objects.create(
            shipment_id="F-3",
            shipment_date="22.10.2026",
            article="13541",
            status=Shipment.STATUS_ERROR,
        )

    def test_filters_by_article(self):
        response = self.client.get(reverse("shipments"), {"article": "13541"})

        self.assertEqual(response.context["filtered_total"], 2)
        self.assertEqual(
            [shipment.shipment_id for shipment in response.context["shipments"]],
            ["F-3", "F-1"],
        )
        self.assertFalse(response.context["live_updates"])

    def test_filters_by_status(self):
        response = self.client.get(reverse("shipments"), {"status": "closed"})

        self.assertEqual(
            [shipment.shipment_id for shipment in response.context["shipments"]],
            ["F-1"],
        )

    def test_filters_by_date(self):
        response = self.client.get(reverse("shipments"), {"date": "2026-10-21"})

        self.assertEqual(
            [shipment.shipment_id for shipment in response.context["shipments"]],
            ["F-2"],
        )

    def test_filters_by_date_range(self):
        response = self.client.get(
            reverse("shipments"),
            {"date_from": "2026-10-21", "date_to": "2026-10-22"},
        )

        self.assertEqual(
            {shipment.shipment_id for shipment in response.context["shipments"]},
            {"F-2", "F-3"},
        )

    def test_filters_are_combined(self):
        response = self.client.get(
            reverse("shipments"),
            {"date_from": "2026-10-21", "article": "13541"},
        )

        self.assertEqual(
            [shipment.shipment_id for shipment in response.context["shipments"]],
            ["F-3"],
        )
        self.assertIn("article=13541", response.context["filter_query"])
        self.assertIn("date_from=2026-10-21", response.context["filter_query"])

    def test_no_filters_enables_live_updates(self):
        response = self.client.get(reverse("shipments"))

        self.assertTrue(response.context["live_updates"])
        self.assertEqual(response.context["filtered_total"], 3)


class ShipmentPaginationTests(TestCase):
    def setUp(self):
        for index in range(105):
            Shipment.objects.create(
                shipment_id=f"P-{index:03d}",
                shipment_date="21.10.2026",
                article="13541",
                status=Shipment.STATUS_CLOSED,
            )

    def test_first_page_has_100_records(self):
        response = self.client.get(reverse("shipments"))

        self.assertEqual(len(response.context["shipments"]), 100)
        self.assertEqual(response.context["page_obj"].number, 1)

    def test_second_page_has_remaining_records(self):
        response = self.client.get(reverse("shipments"), {"page": 2})

        self.assertEqual(len(response.context["shipments"]), 5)
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertFalse(response.context["live_updates"])

    def test_pagination_keeps_filters(self):
        response = self.client.get(
            reverse("shipments"),
            {"article": "13541", "page": 2},
        )

        self.assertEqual(response.context["filter_query"], "article=13541&")
