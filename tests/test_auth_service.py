"""Account and privacy tests; runnable by unittest and PyTest."""

import tempfile
import unittest

from src.data.json_repository import JsonRepository
from src.services.audit_service import AuditService
from src.services.auth_service import AuthService
from src.services.profile_service import ProfileService


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = JsonRepository(self.temp.name)
        self.audit = AuditService(self.repo)
        self.auth = AuthService(self.repo, self.audit)
        self.profiles = ProfileService(self.repo, self.audit)
        self.admin = self.auth.bootstrap_admin("admin", "admin-password")

    def tearDown(self):
        self.temp.cleanup()

    def test_password_is_hashed_and_invalid_login_rejected(self):
        stored = self.repo.read("users")[0]
        self.assertNotIn("admin-password", str(stored))
        self.assertEqual(self.auth.authenticate("admin", "admin-password")["role"], "Admin")
        with self.assertRaises(ValueError):
            self.auth.authenticate("admin", "wrong-password")

    def test_volunteer_cannot_read_client_profile(self):
        volunteer = self.auth.create_user(self.admin, "volunteer", "password-123", "Volunteer")
        client = self.auth.create_user(self.admin, "client", "password-123", "Client")
        self.profiles.save_profile(client, client["id"], household_size=1,
                                   dietary_requirements=["None"], allergies=["Peanut"],
                                   cultural_requirements=["None"], consent=True)
        with self.assertRaises(PermissionError):
            self.profiles.get_profile(volunteer, client["id"])
        with self.assertRaises(PermissionError):
            self.profiles.list_profiles(volunteer)

    def test_first_profile_save_needs_consent_and_valid_household(self):
        client = self.auth.create_user(self.admin, "client", "password-123", "Client")
        details = {"dietary_requirements": ["None"], "allergies": ["None"],
                   "cultural_requirements": ["None"]}
        with self.assertRaises(ValueError):
            self.profiles.save_profile(client, client["id"], household_size=1,
                                       consent=False, **details)
        with self.assertRaises(ValueError):
            self.profiles.save_profile(client, client["id"], household_size=0,
                                       consent=True, **details)
        self.assertIsNone(self.profiles.get_profile(client, client["id"]))

    def test_role_change_applies_on_next_login_and_is_audited(self):
        user = self.auth.create_user(self.admin, "helper", "password-123", "Volunteer")
        self.auth.change_user(self.admin, user["id"], role="Staff")
        self.assertEqual(user["role"], "Volunteer")
        self.assertEqual(self.auth.authenticate("helper", "password-123")["role"], "Staff")
        actions = [entry["action"] for entry in self.audit.list_entries(self.admin)]
        self.assertIn("role_changed", actions)

    def test_admin_cannot_modify_another_admin(self):
        other = self.auth.create_user(self.admin, "other", "password-123", "Admin")
        with self.assertRaises(PermissionError):
            self.auth.change_user(self.admin, other["id"], active=False)


if __name__ == "__main__":
    unittest.main()
