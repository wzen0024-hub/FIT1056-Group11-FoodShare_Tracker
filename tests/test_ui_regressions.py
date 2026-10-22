"""Streamlit AppTest regression flows for the functional fixes (needs `pip install -r requirements.txt`).

Each test drives the real screens in main.py with synthetic accounts and a temporary data folder
(FOODSHARE_DATA_DIR), so the project's data/*.json files are never touched. Existing flows stay in
tests/test_ui_flows.py; this file adds the new ones.
"""

import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

from app import client_ui
from src.data.json_repository import JsonRepository
from src.services.audit_service import AuditService
from src.services.auth_service import AuthService
from src.services.donation_service import DonationService
from src.services.hamper_service import HamperService
from src.services.inventory_service import InventoryService
from src.services.profile_service import ProfileService


APP = str(Path(__file__).resolve().parents[1] / "main.py")
CHECKLIST = "I have checked that my food is safe, correctly stored and within expiry"


def widget(items, label):
    """First element whose label matches exactly (same helper as tests/test_ui_flows.py)."""
    return next(item for item in items if item.label == label)


def choose(selectbox, text):
    """Pick the option whose displayed text starts with `text` (options are shown as formatted strings)."""
    index = next(i for i, option in enumerate(selectbox.options) if option.startswith(text))
    return selectbox.select_index(index)


class UiTestCase(unittest.TestCase):
    """Shared setup: temporary data folder, one account per role, services on the same folder."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous_dir = os.environ.get("FOODSHARE_DATA_DIR")
        os.environ["FOODSHARE_DATA_DIR"] = self.temp.name
        st.cache_resource.clear()  # services() is cached per process; start each test on its own folder
        self.repo = JsonRepository(self.temp.name)
        self.audit = AuditService(self.repo)
        self.auth = AuthService(self.repo, self.audit)
        self.profiles = ProfileService(self.repo, self.audit)
        self.inventory = InventoryService(self.repo)
        self.hampers = HamperService(self.repo, self.profiles)
        self.donations = DonationService(self.repo)
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

    def sign_in(self, username, password):
        """Use the real login form, as a user who just logged out would."""
        app = AppTest.from_file(APP, default_timeout=15)
        app.run()
        widget(app.text_input, "Username").set_value(username)
        widget(app.text_input, "Password").set_value(password)
        widget(app.button, "Sign in").click().run()
        return app

    def add_item(self, name, *, allergens=("None",), dietary=("None",), quantity=3, days=5):
        return self.inventory.add_item(self.staff, name=name, category="Food", quantity=quantity,
                                       expiry_date=date.today() + timedelta(days=days),
                                       allergen_tags=list(allergens), dietary_tags=list(dietary))


class LoginUiTests(UiTestCase):
    def test_sign_in_fields_use_username_and_current_password_autocomplete(self):
        app = AppTest.from_file(APP, default_timeout=15)
        app.run()
        # .proto is the message Streamlit sends to the browser; it carries the HTML autocomplete value.
        self.assertEqual(widget(app.text_input, "Username").proto.autocomplete, "username")
        self.assertEqual(widget(app.text_input, "Password").proto.autocomplete, "current-password")

    def test_new_password_fields_keep_new_password_autocomplete(self):
        app = self.app_for(self.admin, "User administration")
        self.assertEqual(widget(app.text_input, "New password (8+ characters)").proto.autocomplete, "new-password")
        self.assertEqual(widget(app.text_input, "New username").proto.autocomplete, "off")

    def test_ac53_wrong_password_is_rejected_and_no_session_starts(self):
        app = self.sign_in("admin", "wrong-password")
        self.assertTrue(any("Invalid username or password" in e.value for e in app.error))
        self.assertIsNone(app.session_state["user"])

    def test_ac57_log_out_ends_the_session_and_shows_the_login_form(self):
        app = self.app_for(self.staff)
        widget(app.sidebar.button, "Log out").click().run()
        self.assertIsNone(app.session_state["user"])
        self.assertIn("Username", [field.label for field in app.text_input])


class AdminAccountUiTests(UiTestCase):
    def create_user_once(self, app, username, role):
        widget(app.text_input, "New username").set_value(username)
        widget(app.text_input, "New password (8+ characters)").set_value("password-123")
        widget(app.selectbox, "Role").select(role)
        widget(app.button, "Create user").click().run()  # ONE click

    def test_a_staff_account_is_created_with_one_click_and_survives_logout_and_login(self):
        app = self.app_for(self.admin, "User administration")
        self.create_user_once(app, "khalid", "Staff")
        self.assertEqual(len(app.exception), 0)
        users = self.repo.read("users")
        self.assertEqual([u["username"] for u in users].count("khalid"), 1)
        self.assertEqual(len(users), 6)  # admin, staff, volunteer, client, donor + khalid
        self.assertIn("khalid (Staff)", widget(app.selectbox, "Account to update").options)

        relogin = self.sign_in("admin", "password-123")  # a new session, as after logging out and in
        widget(relogin.radio, "Page").set_value("User administration").run()
        self.assertIn("khalid (Staff)", widget(relogin.selectbox, "Account to update").options)

    def test_b_client_to_staff_needs_one_save_and_applies_at_next_login(self):
        self.auth.create_user(self.admin, "khalid", "password-123", "Client")
        app = self.app_for(self.admin, "User administration")
        choose(widget(app.selectbox, "Account to update"), "khalid").run()
        # The role selector must now show the selected account's stored role.
        self.assertEqual(widget(app.selectbox, "New role").value, "Client")
        widget(app.selectbox, "New role").select("Staff")
        widget(app.button, "Save account").click().run()  # ONE click
        self.assertEqual(len(app.exception), 0)
        stored = {u["username"]: u["role"] for u in self.repo.read("users")}
        self.assertEqual(stored["khalid"], "Staff")
        options = widget(app.selectbox, "Account to update").options
        self.assertIn("khalid (Staff)", options)  # still listed, with the new role
        self.assertTrue(any("Account updated: khalid" in s.value for s in app.success))

        khalid = self.sign_in("khalid", "password-123")  # FR-05.6: the new role starts at the next login
        self.assertEqual(khalid.session_state["user"]["role"], "Staff")
        self.assertIn("Client profiles", widget(khalid.radio, "Page").options)

    def test_c_other_admins_are_not_editable_and_nothing_sensitive_is_listed(self):
        other = self.auth.create_user(self.admin, "other-admin", "password-123", "Admin")
        app = self.app_for(self.admin, "User administration")
        options = widget(app.selectbox, "Account to update").options
        self.assertNotIn("other-admin (Admin)", options)
        self.assertIn("staff (Staff)", options)
        self.assertNotIn("password_hash", str([table.value for table in app.dataframe]))
        self.assertNotIn("pbkdf2", str(options))
        self.assertEqual(self.auth.list_users(self.admin)[-1]["id"], other["id"])  # the table still lists them

    def test_role_change_is_audited_and_the_access_log_shows_names(self):
        app = self.app_for(self.admin, "User administration")
        choose(widget(app.selectbox, "Account to update"), "client").run()
        widget(app.selectbox, "New role").select("Volunteer")
        widget(app.button, "Save account").click().run()
        self.assertIn("role_changed", [e["action"] for e in self.repo.read("access_log")])
        log_table = app.dataframe[-1].value
        self.assertIn("role_changed", list(log_table["Action"]))
        self.assertIn("admin", list(log_table["Acting user"]))

    def test_uc10_empty_access_log_says_no_entries_to_show(self):
        self.repo.write("access_log", [])
        app = self.app_for(self.admin, "User administration")
        self.assertTrue(any("No entries to show." in info.value for info in app.info))


class ProfileFieldUiTests(UiTestCase):
    def test_client_saves_accessibility_needs_and_communication_method(self):
        app = self.app_for(self.client)
        widget(app.text_area, client_ui.ACCESSIBILITY_LABEL).set_value("Step-free access please")
        widget(app.selectbox, client_ui.COMMUNICATION_LABEL).select("Phone call")
        widget(app.checkbox, "I confirm consent to store this sensitive profile").set_value(True)
        widget(app.button, "Save profile").click().run()
        self.assertEqual(len(app.exception), 0)
        stored = self.repo.read("profiles")[0]
        self.assertEqual(stored["accessibility_needs"], "Step-free access please")
        self.assertEqual(stored["preferred_communication"], "Phone call")

    def test_form_explains_each_sensitive_field_and_offers_no_restrictions(self):
        app = self.app_for(self.client)
        labels = [w.label for w in list(app.number_input) + list(app.multiselect) + list(app.text_area)]
        for label in labels:
            self.assertIn(" — ", label)  # "<field> — <why it is collected>" (FR-01.8)
        self.assertIn("does not send messages", client_ui.COMMUNICATION_LABEL)
        dietary = widget(app.multiselect, "Dietary requirements — needed to choose suitable food")
        self.assertIn("No restrictions", dietary.options)
        self.assertEqual(widget(app.selectbox, client_ui.COMMUNICATION_LABEL).options,
                         ["Not specified", "SMS", "Phone call", "Email", "In person"])

    def test_staff_edit_keeps_the_note_and_does_not_leak_it_to_the_client(self):
        app = self.app_for(self.staff, "Client profiles")
        widget(app.text_area, "Staff-only substitution note").set_value("Prefers rice over bread")
        widget(app.text_area, client_ui.ACCESSIBILITY_LABEL).set_value("Large print")
        widget(app.checkbox, "I confirm consent to store this sensitive profile").set_value(True)
        widget(app.button, "Save profile").click().run()
        self.assertEqual(self.repo.read("profiles")[0]["substitution_note"], "Prefers rice over bread")
        client_app = self.app_for(self.client)
        self.assertNotIn("Staff-only substitution note", [w.label for w in client_app.text_area])
        self.assertEqual(widget(client_app.text_area, client_ui.ACCESSIBILITY_LABEL).value, "Large print")


class InventoryUiTests(UiTestCase):
    def fill_item_form(self, app, allergens, dietary):
        widget(app.text_input, "Item name").set_value("Rice")
        widget(app.text_input, "Category").set_value("Dry goods")
        widget(app.number_input, "Quantity").set_value(2)
        widget(app.multiselect, "Allergen tags (select None if none)").set_value(allergens)
        widget(app.multiselect, "Dietary suitability tags (select None if none)").set_value(dietary)
        widget(app.button, "Add item").click().run()

    def test_none_cannot_be_combined_with_real_tags_but_other_combinations_save(self):
        app = self.app_for(self.staff, "Inventory")
        self.fill_item_form(app, ["None", "Peanut"], ["None"])
        self.assertTrue(any("None or specific tags" in e.value for e in app.error))
        self.fill_item_form(app, ["Peanut"], ["None", "Vegan"])
        self.assertEqual(self.repo.read("inventory"), [])
        self.fill_item_form(app, [], ["None"])  # missing selection
        self.assertTrue(any("at least one allergen" in e.value for e in app.error))
        self.assertEqual(self.repo.read("inventory"), [])
        self.fill_item_form(app, ["Peanut", "Soy"], ["Vegan", "Halal"])
        self.assertEqual(self.repo.read("inventory")[0]["allergen_tags"], ["Peanut", "Soy"])
        # AC-21: both kinds of tag are shown on the item in the inventory list.
        shown = " ".join([m.value for m in app.markdown] + [e.value for e in app.error])
        self.assertIn("allergens: Peanut, Soy", shown)
        self.assertIn("dietary: Vegan, Halal", shown)
        self.fill_item_form(app, ["None"], ["None"])
        self.assertEqual(len(self.repo.read("inventory")), 2)

    def test_ac14_list_is_earliest_expiry_first_and_near_expiry_is_highlighted(self):
        self.add_item("Later", days=10)
        self.add_item("Tomorrow", days=1)
        app = self.app_for(self.staff, "Inventory")
        highlighted = [e.value for e in app.error]
        self.assertEqual(len(highlighted), 1)
        self.assertIn("Tomorrow", highlighted[0])
        self.assertIn("expires within 48 hours", highlighted[0])
        listed = [m.value for m in app.markdown if "qty" in m.value]
        self.assertTrue(listed[0].startswith("Later"))  # the highlighted item is drawn as st.error, not markdown

    def test_flagged_issue_appears_immediately_and_on_the_next_visit(self):
        self.add_item("Beans")
        app = self.app_for(self.volunteer, "Inventory")
        widget(app.selectbox, "Reason").select("Damaged")
        widget(app.text_input, "Comment").set_value("Tin is dented")
        widget(app.button, "Submit issue").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("Damaged" in w.value and "Tin is dented" in w.value for w in app.warning))
        reopened = self.app_for(self.staff, "Inventory")
        self.assertTrue(any("Damaged" in w.value and "Tin is dented" in w.value for w in reopened.warning))

    def test_admin_sees_flags_but_gets_no_flag_form(self):
        item = self.add_item("Beans")
        self.inventory.flag_issue(self.staff, item["id"], "Spoiled", "Smells off")
        app = self.app_for(self.admin, "Inventory")
        self.assertTrue(any("Spoiled" in w.value and "Smells off" in w.value for w in app.warning))
        self.assertNotIn("Submit issue", [b.label for b in app.button])


class HamperUiTests(UiTestCase):
    def setUp(self):
        super().setUp()
        self.profiles.save_profile(self.client, self.client["id"], household_size=2,
                                   dietary_requirements=["Halal"], allergies=["Peanut"],
                                   cultural_requirements=["None"], consent=True,
                                   substitution_note="Private staff note",
                                   accessibility_needs="Private accessibility text")
        self.safe = self.add_item("Basmati rice", dietary=["Halal"])
        self.unsafe = self.add_item("Trail mix", allergens=["Peanut"], dietary=["Halal"])
        self.hamper = self.hampers.generate(self.staff, self.client["id"])

    def try_adding(self, app, item_name):
        choose(app.selectbox(key=f"candidate-{self.hamper['id']}"), item_name).run()
        app.button(key=f"add-{self.hamper['id']}").click().run()

    def test_volunteer_packing_view_shows_only_hamper_id_item_and_quantity(self):
        app = self.app_for(self.volunteer)
        self.assertEqual([s.value for s in app.subheader], [f"Hamper {self.hamper['id']}"])
        table = app.dataframe[0].value
        self.assertEqual(list(table.columns), ["Item", "Quantity"])
        self.assertEqual(table.to_dict("records"), [{"Item": "Basmati rice", "Quantity": 1}])
        visible = " ".join(str(e.value) for e in list(app.subheader) + list(app.markdown) + list(app.caption)
                           + list(app.info) + list(app.warning) + list(app.error)) + str(table)
        for hidden in (self.client["id"], "client_id", "item_id", self.safe["id"], "Peanut", "Halal",
                       "allergy", "Private staff note", "Private accessibility text"):
            self.assertNotIn(hidden, visible)

    def test_ac33_volunteer_warning_hides_the_reason_and_staff_warning_names_it(self):
        volunteer_app = self.app_for(self.volunteer)
        self.try_adding(volunteer_app, "Trail mix")
        messages = [e.value for e in volunteer_app.error]
        self.assertEqual(messages, ["Warning: item cannot be added to this hamper"])
        staff_app = self.app_for(self.staff, "Safe hampers")
        self.try_adding(staff_app, "Trail mix")
        staff_messages = " ".join(e.value for e in staff_app.error)
        self.assertIn("item cannot be added", staff_messages)
        self.assertIn("Peanut", staff_messages)
        stored = self.repo.read("hampers")[0]
        self.assertEqual([line["item_id"] for line in stored["items"]], [self.safe["id"]])  # still blocked

    def test_uc07_empty_packing_view_message(self):
        self.hampers.mark_packed(self.volunteer, self.hamper["id"])
        app = self.app_for(self.volunteer)
        self.assertTrue(any("No pending hampers at the moment." in i.value for i in app.info))

    def test_ac34_staff_history_shows_date_and_items(self):
        app = self.app_for(self.staff, "Safe hampers")
        history = next(t.value for t in app.dataframe if "Date" in list(t.value.columns))
        self.assertEqual(history.to_dict("records"),
                         [{"Date": date.today().isoformat(), "Status": "Pending", "Items": "Basmati rice × 1"}])


class DonorUiTests(UiTestCase):
    def setUp(self):
        super().setUp()
        self.day = date.today() + timedelta(days=1)
        self.later = date.today() + timedelta(days=3)
        self.empty = date.today() + timedelta(days=2)
        self.slot = self.donations.define_slot(self.staff, self.day, "10:00")
        self.donations.define_slot(self.staff, self.later, "11:00")

    def submit_offer(self, app, rows):
        """rows: list of (category, quantity) for lines 1..n of the offer form."""
        for number, (category, quantity) in enumerate(rows, start=1):
            suffix = "" if number == 1 else f" {number}"
            widget(app.text_input, f"Item category{suffix}").set_value(category)
            widget(app.number_input, f"Estimated quantity{suffix}").set_value(quantity)
        widget(app.button, "Submit offer").click().run()

    def test_ac44_priority_categories_are_shown_before_the_offer_form(self):
        self.donations.set_priorities(self.staff, ["Rice", "Tinned fish"])
        app = self.app_for(self.donor)
        self.assertTrue(any("Rice" in i.value and "Tinned fish" in i.value for i in app.info))

    def test_offer_with_two_categories_is_saved_once(self):
        app = self.app_for(self.donor)
        self.submit_offer(app, [("Rice", 3), ("Fruit", 2)])
        self.assertEqual(len(app.exception), 0)
        offers = self.repo.read("donations")["offers"]
        self.assertEqual([o["items"] for o in offers], [{"Rice": 3, "Fruit": 2}])

    def test_invalid_offers_are_prevented_with_a_clear_message(self):
        cases = {"needs a name": [("", 4)],                          # AC-36 blank category
                 "greater than zero": [("Rice", 0)],                  # AC-37 zero quantity
                 "at least one item category": [("", 0)],            # nothing entered
                 "more than once": [("Rice", 1), ("rice", 2)]}        # repeated category, never overwritten
        for expected, rows in cases.items():
            with self.subTest(expected=expected):
                app = self.app_for(self.donor)
                self.submit_offer(app, rows)
                self.assertTrue(any(expected in e.value for e in app.error), expected)
        self.assertEqual(self.repo.read("donations").get("offers", []), [])

    def test_date_with_slots_shows_only_that_dates_free_slots(self):
        self.donations.submit_offer(self.donor, {"Rice": 1})
        app = self.app_for(self.donor)
        self.assertEqual(widget(app.selectbox, "Available time").options, [f"{self.day.isoformat()} 10:00"])
        widget(app.date_input, "Drop-off date").set_value(self.later).run()
        self.assertEqual(widget(app.selectbox, "Available time").options, [f"{self.later.isoformat()} 11:00"])

    def test_ac41_date_without_slots_prompts_for_an_alternative_and_blocks_booking(self):
        self.donations.submit_offer(self.donor, {"Rice": 1})
        app = self.app_for(self.donor)
        widget(app.date_input, "Drop-off date").set_value(self.empty).run()
        self.assertTrue(any("alternative date" in w.value for w in app.warning))
        self.assertNotIn("Confirm booking", [b.label for b in app.button])

    def test_no_slots_anywhere_explains_and_blocks_booking(self):
        self.repo.write("donations", {"offers": [], "slots": []})  # remove the slots created in setUp
        self.donations.submit_offer(self.donor, {"Rice": 1})
        app = self.app_for(self.donor)
        self.assertTrue(any("no bookable drop-off slots" in w.value for w in app.warning))
        self.assertNotIn("Confirm booking", [b.label for b in app.button])

    def test_booked_slot_gives_a_receipt_and_is_no_longer_offered_to_others(self):
        self.donations.submit_offer(self.donor, {"Rice": 1})
        app = self.app_for(self.donor)
        widget(app.checkbox, CHECKLIST).set_value(True)
        widget(app.button, "Confirm booking").click().run()
        self.assertTrue(any("Booking confirmed" in s.value and "Receipt:" in s.value for s in app.success))
        self.assertIsNotNone(self.repo.read("donations")["slots"][0]["offer_id"])
        other = self.auth.create_user(self.admin, "donor2", "password-123", "Donor")
        self.donations.submit_offer(other, {"Beans": 2})
        other_app = self.app_for(other)
        self.assertEqual(widget(other_app.selectbox, "Available time").options,
                         [f"{self.later.isoformat()} 11:00"])


if __name__ == "__main__":
    unittest.main()
