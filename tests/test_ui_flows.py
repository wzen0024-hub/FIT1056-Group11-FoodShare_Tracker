"""Actor-level Streamlit acceptance flows using synthetic accounts and data."""

import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

from src.data.json_repository import JsonRepository
from src.services.audit_service import AuditService
from src.services.auth_service import AuthService
from src.services.donation_service import DonationService
from src.services.inventory_service import InventoryService
from src.services.profile_service import ProfileService


APP = str(Path(__file__).resolve().parents[1] / "main.py")


def widget(items, label):
    return next(item for item in items if item.label == label)


class UiFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous_dir = os.environ.get("FOODSHARE_DATA_DIR")
        os.environ["FOODSHARE_DATA_DIR"] = self.temp.name
        st.cache_resource.clear()
        self.repo = JsonRepository(self.temp.name)
        self.audit = AuditService(self.repo)
        self.auth = AuthService(self.repo, self.audit)
        self.admin = self.auth.bootstrap_admin("admin", "password-123")
        self.staff = self.auth.create_user(self.admin, "staff", "password-123", "Staff")
        self.volunteer = self.auth.create_user(self.admin, "volunteer", "password-123", "Volunteer")
        self.client = self.auth.create_user(self.admin, "client", "password-123", "Client")
        self.donor = self.auth.create_user(self.admin, "donor", "password-123", "Donor")

    def tearDown(self):
        st.cache_resource.clear()
        if self.previous_dir is None:
            os.environ.pop("FOODSHARE_DATA_DIR", None)
        else:
            os.environ["FOODSHARE_DATA_DIR"] = self.previous_dir
        self.temp.cleanup()

    def app_for(self, actor, page=None):
        app = AppTest.from_file(APP, default_timeout=15)
        app.session_state["user"] = actor
        app.run()
        if page:
            widget(app.radio, "Page").set_value(page).run()
        self.assertEqual(len(app.exception), 0)
        return app

    def test_f01_client_consent_form(self):
        app = self.app_for(self.client)
        widget(app.button, "Save profile").click().run()
        self.assertTrue(any("Consent is required" in e.value for e in app.error))
        self.assertEqual(self.repo.read("profiles"), [])
        widget(app.checkbox, "I confirm consent to store this sensitive profile").set_value(True)
        widget(app.button, "Save profile").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(self.repo.read("profiles")), 1)

    def test_f02_staff_inventory_quantity_boundary(self):
        app = self.app_for(self.staff, "Inventory")
        widget(app.text_input, "Item name").set_value("Rice")
        widget(app.text_input, "Category").set_value("Dry goods")
        widget(app.multiselect, "Allergen tags (select None if none)").set_value(["None"])
        widget(app.multiselect, "Dietary suitability tags (select None if none)").set_value(["None"])
        widget(app.button, "Add item").click().run()
        self.assertTrue(any("Quantity must be greater than zero" in e.value for e in app.error))
        self.assertEqual(self.repo.read("inventory"), [])
        widget(app.number_input, "Quantity").set_value(1)
        widget(app.button, "Add item").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(self.repo.read("inventory")[0]["quantity"], 1)

    def test_f03_staff_generates_safe_list_and_volunteer_sees_no_client(self):
        ProfileService(self.repo, self.audit).save_profile(
            self.client, self.client["id"], household_size=1,
            dietary_requirements=["None"], allergies=["Peanut"],
            cultural_requirements=["None"], consent=True)
        inventory = InventoryService(self.repo)
        for name, tags in (("Peanut bar", ["Peanut"]), ("Rice", ["None"])):
            inventory.add_item(self.staff, name=name, category="Food", quantity=1,
                               expiry_date=date.today() + timedelta(days=2),
                               allergen_tags=tags, dietary_tags=["None"])
        staff_app = self.app_for(self.staff, "Safe hampers")
        widget(staff_app.button, "Generate Safe Packing List").click().run()
        hamper = self.repo.read("hampers")[0]
        self.assertEqual([line["name"] for line in hamper["items"]], ["Rice"])
        volunteer_app = self.app_for(self.volunteer)
        self.assertEqual([r.value for r in volunteer_app.header], ["Packing view"])
        self.assertNotIn("Client profiles", widget(volunteer_app.radio, "Page").options)
        self.assertNotIn(self.client["id"], str(volunteer_app))

    def test_f04_donor_checklist_and_receipt(self):
        slot = DonationService(self.repo).define_slot(
            self.staff, date.today() + timedelta(days=1), "12:00")
        app = self.app_for(self.donor)
        widget(app.text_input, "Item category").set_value("Vegetables")
        widget(app.button, "Submit offer").click().run()
        self.assertEqual(len(self.repo.read("donations")["offers"]), 1)
        widget(app.button, "Confirm booking").click().run()
        self.assertTrue(any("Acknowledge" in e.value for e in app.error))
        self.assertIsNone(self.repo.read("donations")["slots"][0]["offer_id"])
        widget(app.checkbox, "I have checked that my food is safe, correctly stored and within expiry").set_value(True)
        widget(app.button, "Confirm booking").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("Booking confirmed" in s.value for s in app.success))
        self.assertIsNotNone(self.repo.read("donations")["slots"][0]["offer_id"])

    def test_f05_volunteer_navigation_excludes_profiles(self):
        app = self.app_for(self.volunteer)
        self.assertEqual(set(widget(app.radio, "Page").options), {"Packing view", "Inventory"})
        with self.assertRaises(PermissionError):
            ProfileService(self.repo, self.audit).list_profiles(self.volunteer)


if __name__ == "__main__":
    unittest.main()
