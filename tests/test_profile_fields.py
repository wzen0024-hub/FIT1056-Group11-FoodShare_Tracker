"""Client profile tests for FR-01.1 (accessibility needs, communication method), FR-01.5 and FR-05.7.

Every test uses a temporary data folder; the real data/*.json files are never touched.
"""

import tempfile
import unittest

from src.data.json_repository import JsonRepository
from src.services.audit_service import AuditService
from src.services.profile_service import ProfileService


STAFF = {"id": "staff-1", "role": "Staff"}
VOLUNTEER = {"id": "volunteer-1", "role": "Volunteer"}
CLIENT = {"id": "client-1", "role": "Client"}
OTHER_CLIENT = {"id": "client-2", "role": "Client"}

BASE = {"household_size": 3, "dietary_requirements": ["Halal"], "allergies": ["Peanut"],
        "cultural_requirements": ["None"], "consent": True}


class ProfileFieldTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = JsonRepository(self.temp.name)
        self.audit = AuditService(self.repo)
        self.profiles = ProfileService(self.repo, self.audit)

    def tearDown(self):
        self.temp.cleanup()

    def test_client_saves_and_reads_back_new_fields(self):
        self.profiles.save_profile(CLIENT, CLIENT["id"], accessibility_needs="  Wheelchair access  ",
                                   preferred_communication="SMS", **BASE)
        stored = self.repo.read("profiles")[0]
        self.assertEqual(stored["accessibility_needs"], "Wheelchair access")
        self.assertEqual(stored["preferred_communication"], "SMS")
        view = self.profiles.get_profile(CLIENT, CLIENT["id"])
        self.assertEqual((view["accessibility_needs"], view["preferred_communication"]),
                         ("Wheelchair access", "SMS"))
        self.assertNotIn("substitution_note", view)

    def test_staff_can_edit_new_fields_and_keep_substitution_note(self):
        self.profiles.save_profile(STAFF, CLIENT["id"], substitution_note="Prefers rice",
                                   accessibility_needs="Large print", preferred_communication="Phone call", **BASE)
        profile = self.profiles.get_profile(STAFF, CLIENT["id"])
        self.assertEqual(profile["substitution_note"], "Prefers rice")
        # A later client save must neither show nor erase the staff-only note.
        self.profiles.save_profile(CLIENT, CLIENT["id"], accessibility_needs="Large print and quiet room",
                                   preferred_communication="Email", **BASE)
        profile = self.profiles.get_profile(STAFF, CLIENT["id"])
        self.assertEqual(profile["substitution_note"], "Prefers rice")
        self.assertEqual(profile["preferred_communication"], "Email")

    def test_clients_cannot_edit_or_read_another_clients_profile(self):
        with self.assertRaises(PermissionError):
            self.profiles.save_profile(OTHER_CLIENT, CLIENT["id"], accessibility_needs="x", **BASE)
        self.profiles.save_profile(CLIENT, CLIENT["id"], **BASE)
        with self.assertRaises(PermissionError):
            self.profiles.get_profile(OTHER_CLIENT, CLIENT["id"])
        with self.assertRaises(PermissionError):
            self.profiles.get_profile(VOLUNTEER, CLIENT["id"])

    def test_omitting_new_fields_keeps_stored_values(self):
        self.profiles.save_profile(CLIENT, CLIENT["id"], accessibility_needs="Hearing loop",
                                   preferred_communication="In person", **BASE)
        self.profiles.save_profile(CLIENT, CLIENT["id"], **BASE)  # an older caller
        profile = self.profiles.get_profile(CLIENT, CLIENT["id"])
        self.assertEqual((profile["accessibility_needs"], profile["preferred_communication"]),
                         ("Hearing loop", "In person"))

    def test_legacy_profile_without_new_fields_loads_with_defaults(self):
        self.repo.write("profiles", [{"id": "p1", "client_id": CLIENT["id"], "household_size": 2,
                                      "dietary_requirements": ["None"], "allergies": ["None"],
                                      "cultural_requirements": ["None"], "consent": True,
                                      "substitution_note": ""}])
        for actor in (CLIENT, STAFF):
            profile = self.profiles.get_profile(actor, CLIENT["id"])
            self.assertEqual(profile["accessibility_needs"], "")
            self.assertEqual(profile["preferred_communication"], "Not specified")
        self.assertEqual(self.profiles.list_profiles(STAFF)[0]["preferred_communication"], "Not specified")
        # Saving upgrades the stored record.
        self.profiles.save_profile(CLIENT, CLIENT["id"], **BASE)
        self.assertIn("accessibility_needs", self.repo.read("profiles")[0])

    def test_invalid_communication_method_and_existing_validation_still_rejected(self):
        with self.assertRaises(ValueError):
            self.profiles.save_profile(CLIENT, CLIENT["id"], preferred_communication="Pigeon", **BASE)
        with self.assertRaises(ValueError):
            self.profiles.save_profile(CLIENT, CLIENT["id"], **{**BASE, "consent": False})
        with self.assertRaises(ValueError):
            self.profiles.save_profile(CLIENT, CLIENT["id"], **{**BASE, "household_size": 0})
        self.assertEqual(self.repo.read("profiles"), [])

    def test_ac10_ac11_household_size_and_dietary_selection_are_validated(self):
        with self.assertRaisesRegex(ValueError, "Household size"):
            self.profiles.save_profile(CLIENT, CLIENT["id"], **{**BASE, "household_size": 0})
        with self.assertRaisesRegex(ValueError, "dietary requirements"):
            self.profiles.save_profile(CLIENT, CLIENT["id"], **{**BASE, "dietary_requirements": []})
        self.assertEqual(self.repo.read("profiles"), [])
        # "No restrictions" is stored as "None" and must be accepted.
        saved = self.profiles.save_profile(CLIENT, CLIENT["id"], **{**BASE, "dietary_requirements": ["None"]})
        self.assertEqual(saved["dietary_requirements"], ["None"])

    def test_delete_requires_confirmation_removes_data_and_logs_without_contents(self):
        self.profiles.save_profile(CLIENT, CLIENT["id"], accessibility_needs="Secret detail", **BASE)
        with self.assertRaises(ValueError):
            self.profiles.delete_own_profile(CLIENT, False)
        self.assertEqual(len(self.repo.read("profiles")), 1)
        self.profiles.delete_own_profile(CLIENT, True)
        self.assertEqual(self.repo.read("profiles"), [])
        entry = self.audit.list_entries({"id": "admin", "role": "Admin"})[0]
        self.assertEqual(entry["action"], "profile_deleted")
        self.assertNotIn("Secret detail", str(self.repo.read("access_log")))
        self.assertNotIn("Peanut", str(self.repo.read("access_log")))

    def test_deleting_a_missing_profile_writes_no_audit_entry(self):
        with self.assertRaises(ValueError):
            self.profiles.delete_own_profile(CLIENT, True)
        self.assertEqual(self.repo.read("access_log"), [])

    def test_saving_and_staff_amendment_are_audited(self):
        self.profiles.save_profile(CLIENT, CLIENT["id"], **BASE)
        self.profiles.save_profile(STAFF, CLIENT["id"], **{**BASE, "allergies": ["Peanut", "Soy"]})
        actions = [(e["actor_id"], e["action"]) for e in self.repo.read("access_log")]
        self.assertEqual(actions, [(CLIENT["id"], "profile_saved"), (STAFF["id"], "profile_saved")])


if __name__ == "__main__":
    unittest.main()
