"""Administrator account-management regression tests (FR-05.1, 05.3-05.6, AC-45, AC-47-AC-50).

Service-level only: they prove that creating, changing and listing accounts persists
correctly. The Streamlit widget behaviour is covered in tests/test_ui_flows.py.
Each test uses its own temporary data folder; the real data/*.json files are never touched.
"""

import tempfile
import unittest

from src.data.json_repository import JsonRepository
from src.services.audit_service import AuditService
from src.services.auth_service import AuthService


def build_services(data_dir):
    """Create new repository/service objects, as a fresh Streamlit rerun or login would."""
    repo = JsonRepository(data_dir)
    audit = AuditService(repo)
    return repo, audit, AuthService(repo, audit)


def label(user):
    """Same text the Account to update selector shows."""
    return f"{user['username']} ({user['role']})"


class AdminAccountTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo, self.audit, self.auth = build_services(self.temp.name)
        self.admin = self.auth.bootstrap_admin("admin", "admin-password")

    def tearDown(self):
        self.temp.cleanup()

    def test_a_create_staff_account_is_saved_once_and_listed_after_relogin(self):
        khalid = self.auth.create_user(self.admin, "khalid", "password-123", "Staff")
        self.assertEqual(len(self.repo.read("users")), 2)  # the Admin plus exactly one new account

        # A new set of services reading the same folder models a rerun / logout / login.
        _, _, fresh_auth = build_services(self.temp.name)
        admin_again = fresh_auth.authenticate("admin", "admin-password")
        self.assertIn(label(khalid), [label(u) for u in fresh_auth.editable_users(admin_again)])
        self.assertEqual(sum(u["username"] == "khalid" for u in fresh_auth.list_users(admin_again)), 1)

    def test_creating_the_same_username_twice_does_not_add_a_second_account(self):
        self.auth.create_user(self.admin, "khalid", "password-123", "Staff")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.auth.create_user(self.admin, "Khalid", "password-123", "Staff")
        self.assertEqual(len(self.repo.read("users")), 2)

    def test_b_change_client_to_staff_persists_and_applies_at_next_login(self):
        self.auth.create_user(self.admin, "khalid", "password-123", "Client")
        other = self.auth.create_user(self.admin, "sara", "password-123", "Client")
        client_session = self.auth.authenticate("khalid", "password-123")
        target = next(u for u in self.auth.editable_users(self.admin) if u["username"] == "khalid")

        self.auth.change_user(self.admin, target["id"], role="Staff", active=True)

        stored = {u["username"]: u for u in self.repo.read("users")}
        self.assertEqual(stored["khalid"]["role"], "Staff")
        self.assertEqual(stored["sara"]["role"], "Client")  # only the selected account changed
        self.assertIn("khalid (Staff)", [label(u) for u in self.auth.editable_users(self.admin)])
        self.assertEqual(client_session["role"], "Client")  # FR-05.6: old session keeps the old role
        self.assertEqual(self.auth.authenticate("khalid", "password-123")["role"], "Staff")
        self.assertEqual(other["role"], "Client")

    def test_c_admin_restrictions_and_audit_are_preserved(self):
        other_admin = self.auth.create_user(self.admin, "other-admin", "password-123", "Admin")
        helper = self.auth.create_user(self.admin, "helper", "password-123", "Volunteer")

        editable_ids = {u["id"] for u in self.auth.editable_users(self.admin)}
        self.assertIn(self.admin["id"], editable_ids)
        self.assertIn(helper["id"], editable_ids)
        self.assertNotIn(other_admin["id"], editable_ids)
        with self.assertRaises(PermissionError):
            self.auth.change_user(self.admin, other_admin["id"], role="Staff")

        self.auth.change_user(self.admin, helper["id"], role="Staff")
        self.auth.change_user(self.admin, helper["id"], active=False)
        self.auth.change_user(self.admin, helper["id"], active=True)
        actions = [entry["action"] for entry in self.audit.list_entries(self.admin)]
        for expected in ("user_created", "role_changed", "user_disabled", "user_enabled"):
            self.assertIn(expected, actions)

    def test_account_lists_never_contain_password_hashes(self):
        self.auth.create_user(self.admin, "helper", "password-123", "Volunteer")
        for row in self.auth.list_users(self.admin) + self.auth.editable_users(self.admin):
            self.assertNotIn("password_hash", row)

    def test_non_admins_cannot_manage_accounts(self):
        staff = self.auth.create_user(self.admin, "staff", "password-123", "Staff")
        for call in (lambda: self.auth.list_users(staff), lambda: self.auth.editable_users(staff),
                     lambda: self.auth.create_user(staff, "x", "password-123", "Client")):
            with self.assertRaises(PermissionError):
                call()

    def test_disabled_account_cannot_log_in(self):
        user = self.auth.create_user(self.admin, "helper", "password-123", "Volunteer")
        self.auth.change_user(self.admin, user["id"], active=False)
        with self.assertRaises(ValueError):
            self.auth.authenticate("helper", "password-123")


if __name__ == "__main__":
    unittest.main()
