"""Safe packing and stock integrity tests."""

import tempfile
import unittest
from datetime import date, timedelta

from src.data.json_repository import JsonRepository
from src.services.audit_service import AuditService
from src.services.hamper_service import HamperService
from src.services.inventory_service import InventoryService
from src.services.profile_service import ProfileService


STAFF = {"id": "staff-1", "role": "Staff"}
VOLUNTEER = {"id": "volunteer-1", "role": "Volunteer"}
CLIENT = {"id": "client-1", "role": "Client"}


class HamperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = JsonRepository(self.temp.name)
        self.profiles = ProfileService(self.repo, AuditService(self.repo))
        self.inventory = InventoryService(self.repo)
        self.hampers = HamperService(self.repo, self.profiles)
        self.profiles.save_profile(CLIENT, CLIENT["id"], household_size=1,
                                   dietary_requirements=["None"], allergies=["Peanut"],
                                   cultural_requirements=["None"], consent=True)

    def tearDown(self):
        self.temp.cleanup()

    def item(self, name, allergens, quantity=1):
        return self.inventory.add_item(STAFF, name=name, category="Food", quantity=quantity,
                                       expiry_date=date.today() + timedelta(days=3),
                                       allergen_tags=allergens, dietary_tags=["None"])

    def test_allergen_excluded_and_volunteer_view_anonymised(self):
        unsafe = self.item("Peanut bar", ["Peanut"])
        safe = self.item("Rice", ["None"])
        hamper = self.hampers.generate(STAFF, CLIENT["id"])
        self.assertEqual([x["item_id"] for x in hamper["items"]], [safe["id"]])
        view = self.hampers.pending_for_packing(VOLUNTEER)[0]
        self.assertNotIn("client_id", view)
        with self.assertRaisesRegex(ValueError, "item cannot be added"):
            self.hampers.add_item(VOLUNTEER, hamper["id"], unsafe["id"])

    def test_pack_deducts_stock_once(self):
        safe = self.item("Rice", ["None"], quantity=2)
        hamper = self.hampers.generate(STAFF, CLIENT["id"])
        self.hampers.mark_packed(VOLUNTEER, hamper["id"])
        stock = next(x for x in self.inventory.list_items(STAFF) if x["id"] == safe["id"])
        self.assertEqual(stock["quantity"], 1)
        with self.assertRaises(ValueError):
            self.hampers.mark_packed(VOLUNTEER, hamper["id"])

    def test_insufficient_stock_does_not_change_inventory(self):
        safe = self.item("Rice", ["None"])
        first = self.hampers.generate(STAFF, CLIENT["id"])
        second = self.hampers.generate(STAFF, CLIENT["id"])
        self.hampers.mark_packed(STAFF, first["id"])
        with self.assertRaises(ValueError):
            self.hampers.mark_packed(STAFF, second["id"])
        stock = next(x for x in self.inventory.list_items(STAFF) if x["id"] == safe["id"])
        self.assertEqual(stock["quantity"], 0)

    def test_changed_allergy_blocks_packing_an_old_list(self):
        self.item("Soy milk", ["Soy"])
        hamper = self.hampers.generate(STAFF, CLIENT["id"])
        self.profiles.save_profile(CLIENT, CLIENT["id"], household_size=1,
                                   dietary_requirements=["None"], allergies=["Peanut", "Soy"],
                                   cultural_requirements=["None"], consent=True)
        with self.assertRaisesRegex(ValueError, "reviewed"):
            self.hampers.mark_packed(VOLUNTEER, hamper["id"])
        self.assertEqual(self.inventory.list_items(STAFF)[0]["quantity"], 1)


if __name__ == "__main__":
    unittest.main()
