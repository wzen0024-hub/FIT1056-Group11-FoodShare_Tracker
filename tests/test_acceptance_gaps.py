"""Service-level evidence for acceptance criteria that previously had no recorded test.

Covers AC-15, AC-23, AC-26, AC-27, AC-29, AC-30, AC-31, AC-34 (hampers and stock),
AC-42 to AC-44 (slots and priorities) and AC-53 to AC-56 (login, role restrictions, access log).
Service-level means "no Streamlit page was opened"; the matching screens are covered in
tests/test_ui_regressions.py.

Every test uses a temporary data folder; the real data/*.json files are never touched.
"""

import tempfile
import unittest
from datetime import date, timedelta

from src.data.json_repository import JsonRepository
from src.services.audit_service import AuditService
from src.services.auth_service import AuthService
from src.services.donation_service import DonationService
from src.services.hamper_service import HamperService
from src.services.inventory_service import InventoryService
from src.services.profile_service import ProfileService


STAFF = {"id": "staff-1", "role": "Staff"}
VOLUNTEER = {"id": "volunteer-1", "role": "Volunteer"}
CLIENT = {"id": "client-1", "role": "Client"}
OTHER_CLIENT = {"id": "client-2", "role": "Client"}
DONOR = {"id": "donor-1", "role": "Donor"}


class HamperAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = JsonRepository(self.temp.name)
        self.profiles = ProfileService(self.repo, AuditService(self.repo))
        self.inventory = InventoryService(self.repo)
        self.hampers = HamperService(self.repo, self.profiles)

    def tearDown(self):
        self.temp.cleanup()

    def profile(self, client, *, dietary=("None",), allergies=("None",)):
        self.profiles.save_profile(client, client["id"], household_size=1,
                                   dietary_requirements=list(dietary), allergies=list(allergies),
                                   cultural_requirements=["None"], consent=True)

    def item(self, name, *, days=5, quantity=10, allergens=("None",), dietary=("None",)):
        return self.inventory.add_item(STAFF, name=name, category="Food", quantity=quantity,
                                       expiry_date=date.today() + timedelta(days=days),
                                       allergen_tags=list(allergens), dietary_tags=list(dietary))

    def stock(self, item):
        return next(row for row in self.inventory.list_items(STAFF) if row["id"] == item["id"])["quantity"]

    def set_hamper_quantity(self, hamper, quantity):
        """The UI can never ask for more than the stock, so tests set the line quantity directly."""
        rows = self.repo.read("hampers")
        next(row for row in rows if row["id"] == hamper["id"])["items"][0]["quantity"] = quantity
        self.repo.write("hampers", rows)

    def test_ac15_packing_three_units_of_ten_leaves_seven_on_the_next_view(self):
        self.profile(CLIENT)
        rice = self.item("Rice", quantity=10)
        hamper = self.hampers.generate(STAFF, CLIENT["id"])
        self.set_hamper_quantity(hamper, 3)
        self.hampers.mark_packed(VOLUNTEER, hamper["id"])
        self.assertEqual(self.stock(rice), 7)

    def test_ac23_packing_three_units_of_two_is_refused_and_stock_stays_two(self):
        self.profile(CLIENT)
        rice = self.item("Rice", quantity=2)
        hamper = self.hampers.generate(STAFF, CLIENT["id"])
        self.set_hamper_quantity(hamper, 3)
        with self.assertRaisesRegex(ValueError, "Insufficient stock"):
            self.hampers.mark_packed(VOLUNTEER, hamper["id"])
        self.assertEqual(self.stock(rice), 2)
        self.assertEqual(self.hampers.pending_for_packing(STAFF)[0]["status"], "Pending")

    def test_ac26_halal_client_receives_only_halal_tagged_items(self):
        self.profile(CLIENT, dietary=["Halal"])
        self.item("Halal chicken", dietary=["Halal"])
        self.item("Pork sausages", dietary=["None"])
        hamper = self.hampers.generate(STAFF, CLIENT["id"])
        self.assertEqual([line["name"] for line in hamper["items"]], ["Halal chicken"])

    def test_ac27_expired_and_zero_quantity_items_are_never_listed(self):
        self.profile(CLIENT)
        good = self.item("Rice")
        # The service refuses to ADD such items, so write them as stale stock would look later.
        stale = [{"id": "expired", "name": "Old milk", "category": "Food", "quantity": 4,
                  "expiry_date": (date.today() - timedelta(days=1)).isoformat(),
                  "allergen_tags": ["None"], "dietary_tags": ["None"], "issues": []},
                 {"id": "empty", "name": "Gone beans", "category": "Food", "quantity": 0,
                  "expiry_date": (date.today() + timedelta(days=9)).isoformat(),
                  "allergen_tags": ["None"], "dietary_tags": ["None"], "issues": []}]
        self.repo.update("inventory", lambda rows: rows.extend(stale))
        hamper = self.hampers.generate(STAFF, CLIENT["id"])
        self.assertEqual([line["item_id"] for line in hamper["items"]], [good["id"]])

    def test_ac29_items_are_listed_earliest_expiry_first(self):
        self.profile(CLIENT)
        self.item("Later", days=20)
        self.item("Soonest", days=2)
        self.item("Middle", days=9)
        hamper = self.hampers.generate(STAFF, CLIENT["id"])
        self.assertEqual([line["name"] for line in hamper["items"]], ["Soonest", "Middle", "Later"])

    def test_ac30_no_suitable_food_gives_a_warning_and_creates_no_hamper(self):
        self.profile(CLIENT, allergies=["Peanut"])
        self.item("Peanut bar", allergens=["Peanut"])
        with self.assertRaisesRegex(ValueError, "No suitable food"):
            self.hampers.generate(STAFF, CLIENT["id"])
        self.assertEqual(self.repo.read("hampers"), [])

    def test_ac31_volunteer_marks_a_pending_hamper_as_packed(self):
        self.profile(CLIENT)
        self.item("Rice")
        hamper = self.hampers.generate(STAFF, CLIENT["id"])
        self.assertEqual(self.hampers.mark_packed(VOLUNTEER, hamper["id"])["status"], "Packed")
        self.assertEqual(self.repo.read("hampers")[0]["status"], "Packed")
        self.assertEqual(self.hampers.pending_for_packing(VOLUNTEER), [])

    def test_ac34_history_lists_date_and_items_for_that_client_only(self):
        self.profile(CLIENT)
        self.profile(OTHER_CLIENT)
        self.item("Rice")
        mine = self.hampers.generate(STAFF, CLIENT["id"])
        self.hampers.generate(STAFF, OTHER_CLIENT["id"])
        history = self.hampers.client_history(STAFF, CLIENT["id"])
        self.assertEqual([h["id"] for h in history], [mine["id"]])
        self.assertEqual(history[0]["created_on"], date.today().isoformat())
        self.assertEqual([line["name"] for line in history[0]["items"]], ["Rice"])
        with self.assertRaises(PermissionError):
            self.hampers.client_history(VOLUNTEER, CLIENT["id"])


class SlotAndPriorityAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = DonationService(JsonRepository(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_ac42_a_slot_defined_by_staff_is_available_to_donors(self):
        day = date.today() + timedelta(days=2)
        slot = self.service.define_slot(STAFF, day, "09:30")
        self.assertEqual([s["id"] for s in self.service.available_slots(DONOR, day)], [slot["id"]])
        for missing in (("", "09:30"), (day, "")):
            with self.assertRaises(ValueError):
                self.service.define_slot(STAFF, *missing)

    def test_ac43_and_ac44_priority_categories_are_stored_and_shown_to_donors(self):
        self.service.set_priorities(STAFF, ["Rice", "Tinned fish", "Rice"])
        self.assertEqual(self.service.priorities(STAFF), ["Rice", "Tinned fish"])
        self.assertEqual(self.service.priorities(DONOR), ["Rice", "Tinned fish"])
        with self.assertRaises(PermissionError):
            self.service.set_priorities(DONOR, ["Anything"])


class AccessControlAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = JsonRepository(self.temp.name)
        self.audit = AuditService(self.repo)
        self.auth = AuthService(self.repo, self.audit)
        self.admin = self.auth.bootstrap_admin("admin", "admin-password")
        self.profiles = ProfileService(self.repo, self.audit)
        self.inventory = InventoryService(self.repo)

    def tearDown(self):
        self.temp.cleanup()

    def test_ac53_wrong_password_and_unknown_user_are_rejected(self):
        for username, password in (("admin", "wrong-password"), ("nobody", "admin-password"), ("", "")):
            with self.subTest(username=username), self.assertRaisesRegex(ValueError, "Invalid username or password"):
                self.auth.authenticate(username, password)

    def test_ac54_a_donor_is_denied_the_inventory_list(self):
        donor = self.auth.create_user(self.admin, "donor", "password-123", "Donor")
        with self.assertRaises(PermissionError):
            self.inventory.list_items(donor)

    def test_ac55_a_client_cannot_open_or_change_another_clients_profile(self):
        first = self.auth.create_user(self.admin, "first", "password-123", "Client")
        second = self.auth.create_user(self.admin, "second", "password-123", "Client")
        self.profiles.save_profile(first, first["id"], household_size=1, dietary_requirements=["None"],
                                   allergies=["Peanut"], cultural_requirements=["None"], consent=True)
        with self.assertRaises(PermissionError):
            self.profiles.get_profile(second, first["id"])
        with self.assertRaises(PermissionError):
            self.profiles.save_profile(second, first["id"], household_size=2, dietary_requirements=["None"],
                                       allergies=["None"], cultural_requirements=["None"], consent=True)
        self.assertEqual(self.profiles.get_profile(first, first["id"])["allergies"], ["Peanut"])

    def test_ac56_only_an_admin_can_read_the_access_log_newest_first(self):
        user = self.auth.create_user(self.admin, "helper", "password-123", "Volunteer")
        self.auth.change_user(self.admin, user["id"], role="Staff")
        entries = self.audit.list_entries(self.admin)
        self.assertEqual([e["action"] for e in entries], ["role_changed", "user_created", "user_created"])
        for entry in entries:
            self.assertTrue(entry["timestamp"])
        for actor in (user, None):
            with self.assertRaises(PermissionError):
                self.audit.list_entries(actor)

    def test_empty_access_log_is_an_empty_list(self):
        fresh = AuditService(JsonRepository(tempfile.mkdtemp(dir=self.temp.name)))
        self.assertEqual(fresh.list_entries(self.admin), [])


if __name__ == "__main__":
    unittest.main()
