"""Role-specific conflict warnings and the Volunteer Packing View (FR-03.2, 03.6, 03.7; AC-28, 32, 33).

Every test uses a temporary data folder; the real data/*.json files are never touched.
"""

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
CLIENT = {"id": "client-secret-id", "role": "Client"}

# Words that must never reach a Volunteer: they would reveal the client's restrictions.
SENSITIVE_WORDS = ("Peanut", "Halal", "allergy", "dietary", "cultural", "requirement", CLIENT["id"])


class HamperConflictTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = JsonRepository(self.temp.name)
        self.profiles = ProfileService(self.repo, AuditService(self.repo))
        self.inventory = InventoryService(self.repo)
        self.hampers = HamperService(self.repo, self.profiles)
        self.profiles.save_profile(CLIENT, CLIENT["id"], household_size=2,
                                   dietary_requirements=["Halal"], allergies=["Peanut"],
                                   cultural_requirements=["None"], consent=True,
                                   accessibility_needs="Private accessibility note")
        self.safe = self.add("Basmati rice", ["None"], ["Halal"], quantity=5)
        self.peanut = self.add("Peanut bar", ["Peanut"], ["Halal"])
        self.not_halal = self.add("Ham", ["None"], ["None"])
        self.hamper = self.hampers.generate(STAFF, CLIENT["id"])

    def tearDown(self):
        self.temp.cleanup()

    def add(self, name, allergens, dietary, quantity=2):
        return self.inventory.add_item(STAFF, name=name, category="Food", quantity=quantity,
                                       expiry_date=date.today() + timedelta(days=5),
                                       allergen_tags=allergens, dietary_tags=dietary)

    def attempt(self, actor, item):
        with self.assertRaises(ValueError) as caught:
            self.hampers.add_item(actor, self.hamper["id"], item["id"])
        return str(caught.exception)

    def test_generated_hamper_contains_only_the_safe_item(self):
        self.assertEqual([line["name"] for line in self.hamper["items"]], ["Basmati rice"])

    def test_staff_is_blocked_and_told_the_specific_allergy(self):
        message = self.attempt(STAFF, self.peanut)
        self.assertIn("item cannot be added", message)
        self.assertIn("Peanut", message)

    def test_staff_is_blocked_and_told_the_specific_dietary_requirement(self):
        message = self.attempt(STAFF, self.not_halal)
        self.assertIn("item cannot be added", message)
        self.assertIn("Halal", message)

    def test_volunteer_is_blocked_with_the_generic_message_only(self):
        for item in (self.peanut, self.not_halal):
            message = self.attempt(VOLUNTEER, item)
            self.assertEqual(message, "Warning: item cannot be added to this hamper")
            for word in SENSITIVE_WORDS:
                self.assertNotIn(word, message)

    def test_unsafe_items_never_enter_the_hamper(self):
        for actor in (STAFF, VOLUNTEER):
            for item in (self.peanut, self.not_halal):
                self.attempt(actor, item)
        stored = self.repo.read("hampers")[0]
        self.assertEqual([line["item_id"] for line in stored["items"]], [self.safe["id"]])

    def test_expired_and_out_of_stock_items_stay_blocked(self):
        rows = self.repo.read("inventory")
        for row in rows:
            if row["id"] == self.safe["id"]:
                row["expiry_date"] = (date.today() - timedelta(days=1)).isoformat()
        self.repo.write("inventory", rows)
        self.assertIn("expired", self.attempt(STAFF, self.safe))
        self.assertEqual(self.attempt(VOLUNTEER, self.safe), "Warning: item cannot be added to this hamper")

    def test_stock_limit_still_blocks_both_roles_with_role_specific_detail(self):
        safe_two = self.add("Red lentils", ["None"], ["Halal"], quantity=1)
        self.hampers.add_item(STAFF, self.hamper["id"], safe_two["id"])
        self.assertIn("units in stock", self.attempt(STAFF, safe_two))
        self.assertEqual(self.attempt(VOLUNTEER, safe_two), "Warning: item cannot be added to this hamper")

    def test_safe_item_can_be_added_by_both_roles(self):
        self.hampers.add_item(VOLUNTEER, self.hamper["id"], self.safe["id"])
        result = self.hampers.add_item(STAFF, self.hamper["id"], self.safe["id"])
        self.assertEqual(next(l for l in result["items"] if l["item_id"] == self.safe["id"])["quantity"], 3)

    def test_volunteer_results_contain_only_hamper_id_names_and_quantities(self):
        view = self.hampers.pending_for_packing(VOLUNTEER)
        self.assertEqual(view, [{"id": self.hamper["id"], "items": [{"name": "Basmati rice", "quantity": 1}]}])
        returned = self.hampers.add_item(VOLUNTEER, self.hamper["id"], self.safe["id"])
        self.assertEqual(set(returned), {"id", "items"})
        self.assertEqual(returned["items"], [{"name": "Basmati rice", "quantity": 2}])
        for payload in (view, returned):
            text = str(payload)
            for word in SENSITIVE_WORDS + ("client_id", "item_id", "Private accessibility note"):
                self.assertNotIn(word, text)

    def test_staff_still_see_full_pending_hampers(self):
        staff_view = self.hampers.pending_for_packing(STAFF)[0]
        self.assertEqual(staff_view["client_id"], CLIENT["id"])
        self.assertEqual(staff_view["items"][0]["item_id"], self.safe["id"])


if __name__ == "__main__":
    unittest.main()
