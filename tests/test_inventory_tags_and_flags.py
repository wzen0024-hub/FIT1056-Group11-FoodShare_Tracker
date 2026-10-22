"""Inventory tag rules (FR-02.6, AC-20/21) and issue flags (FR-02.7, AC-22, UC-08).

Every test uses a temporary data folder; the real data/*.json files are never touched.
"""

import tempfile
import unittest
from datetime import date, timedelta

from src.data.json_repository import JsonRepository
from src.services.inventory_service import InventoryService


STAFF = {"id": "staff-1", "role": "Staff"}
VOLUNTEER = {"id": "volunteer-1", "role": "Volunteer"}
ADMIN = {"id": "admin-1", "role": "Admin"}
DONOR = {"id": "donor-1", "role": "Donor"}
CLIENT = {"id": "client-1", "role": "Client"}


class InventoryTagTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.inventory = InventoryService(JsonRepository(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def add(self, allergens, dietary):
        return self.inventory.add_item(STAFF, name="Rice", category="Dry goods", quantity=1,
                                       expiry_date=date.today() + timedelta(days=5),
                                       allergen_tags=allergens, dietary_tags=dietary)

    def test_valid_combinations_are_saved_with_their_tags(self):
        item = self.add(["Peanut", "Soy"], ["Vegan", "Halal"])
        self.assertEqual(item["allergen_tags"], ["Peanut", "Soy"])
        self.assertEqual(item["dietary_tags"], ["Vegan", "Halal"])
        self.assertEqual(self.add(["None"], ["None"])["allergen_tags"], ["None"])
        self.assertEqual(len(self.inventory.list_items(STAFF)), 2)

    def test_missing_tag_selection_is_rejected(self):
        for allergens, dietary in ((None, ["None"]), (["None"], None), ([], ["None"]), (["None"], []),
                                   (None, None)):
            with self.subTest(allergens=allergens, dietary=dietary), self.assertRaises(ValueError):
                self.add(allergens, dietary)
        self.assertEqual(self.inventory.list_items(STAFF), [])

    def test_none_cannot_be_combined_with_real_tags(self):
        for allergens, dietary in ((["None", "Peanut"], ["None"]), (["None"], ["None", "Vegan"]),
                                   (["Peanut", "None"], ["Vegan", "None"])):
            with self.subTest(allergens=allergens, dietary=dietary), self.assertRaisesRegex(ValueError, "None"):
                self.add(allergens, dietary)
        self.assertEqual(self.inventory.list_items(STAFF), [])


class InventoryIssueFlagTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.inventory = InventoryService(JsonRepository(self.temp.name))
        self.item = self.inventory.add_item(STAFF, name="Beans", category="Tins", quantity=4,
                                            expiry_date=date.today() + timedelta(days=30),
                                            allergen_tags=["None"], dietary_tags=["None"])

    def tearDown(self):
        self.temp.cleanup()

    def test_volunteer_flag_is_returned_with_the_item(self):
        self.inventory.flag_issue(VOLUNTEER, self.item["id"], "Damaged", "  Dented tins  ")
        listed = next(i for i in self.inventory.list_items(STAFF) if i["id"] == self.item["id"])
        self.assertEqual([(i["reason"], i["comment"]) for i in listed["issues"]],
                         [("Damaged", "Dented tins")])
        # The Admin's read-only inventory list and the Volunteer's list show the same flag.
        for actor in (VOLUNTEER, ADMIN):
            seen = self.inventory.list_items(actor)[0]
            self.assertEqual(seen["issues"][0]["reason"], "Damaged")

    def test_several_flags_accumulate_and_staff_may_flag(self):
        self.inventory.flag_issue(STAFF, self.item["id"], "Spoiled", "Swollen lid")
        self.inventory.flag_issue(VOLUNTEER, self.item["id"], "Incorrect count", "Only 3 on shelf")
        reasons = [i["reason"] for i in self.inventory.list_items(STAFF)[0]["issues"]]
        self.assertEqual(reasons, ["Spoiled", "Incorrect count"])

    def test_other_roles_cannot_flag(self):
        for actor in (DONOR, CLIENT, ADMIN, None):
            with self.subTest(role=actor and actor["role"]), self.assertRaises(PermissionError):
                self.inventory.flag_issue(actor, self.item["id"], "Damaged", "x")
        self.assertEqual(self.inventory.list_items(STAFF)[0]["issues"], [])

    def test_invalid_flags_are_rejected(self):
        for reason, comment in (("Damaged", "  "), ("Lost", "x"), ("", "x")):
            with self.subTest(reason=reason, comment=comment), self.assertRaises(ValueError):
                self.inventory.flag_issue(STAFF, self.item["id"], reason, comment)
        with self.assertRaises(ValueError):
            self.inventory.flag_issue(STAFF, "missing-id", "Damaged", "x")

    def test_items_saved_before_flags_existed_list_with_an_empty_issue_list(self):
        repo = JsonRepository(self.temp.name)
        rows = repo.read("inventory")
        del rows[0]["issues"]
        repo.write("inventory", rows)
        self.assertEqual(self.inventory.list_items(STAFF)[0]["issues"], [])


if __name__ == "__main__":
    unittest.main()
