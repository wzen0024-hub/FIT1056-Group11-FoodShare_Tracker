"""Inventory boundary and expiry tests."""

import tempfile
import unittest
from datetime import date, timedelta

from src.data.json_repository import JsonRepository
from src.services.inventory_service import InventoryService


STAFF = {"id": "staff-1", "role": "Staff"}


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.inventory = InventoryService(JsonRepository(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def add(self, quantity, day):
        return self.inventory.add_item(STAFF, name="Rice", category="Dry goods",
                                       quantity=quantity, expiry_date=day,
                                       allergen_tags=["None"], dietary_tags=["None"])

    def test_zero_and_negative_quantity_rejected(self):
        for quantity in (0, -1):
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                self.add(quantity, date.today())
        self.assertEqual(self.inventory.list_items(STAFF), [])

    def test_yesterday_rejected_today_accepted(self):
        with self.assertRaises(ValueError):
            self.add(1, date.today() - timedelta(days=1))
        self.add(1, date.today())
        self.assertEqual(len(self.inventory.list_items(STAFF)), 1)

    def test_inventory_sorted_by_expiry_and_near_expiry_marked(self):
        self.add(2, date.today() + timedelta(days=10))
        self.add(2, date.today() + timedelta(days=1))
        rows = self.inventory.list_items(STAFF)
        self.assertTrue(rows[0]["expires_soon"])
        self.assertFalse(rows[1]["expires_soon"])


if __name__ == "__main__":
    unittest.main()
