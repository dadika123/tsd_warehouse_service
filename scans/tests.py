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
