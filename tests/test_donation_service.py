"""Donation safety checklist and slot conflict tests."""

import tempfile
import unittest
from datetime import date, timedelta

from src.data.json_repository import JsonRepository
from src.services.donation_service import DonationService


STAFF = {"id": "staff-1", "role": "Staff"}
DONOR = {"id": "donor-1", "role": "Donor"}
OTHER_DONOR = {"id": "donor-2", "role": "Donor"}


class DonationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = DonationService(JsonRepository(self.temp.name))
        self.day = date.today() + timedelta(days=1)

    def tearDown(self):
        self.temp.cleanup()

    def test_checklist_required_and_slot_booked_once(self):
        slot = self.service.define_slot(STAFF, self.day, "12:00")
        first = self.service.submit_offer(DONOR, {"Vegetables": 3})
        second = self.service.submit_offer(OTHER_DONOR, {"Fruit": 2})
        with self.assertRaisesRegex(ValueError, "checklist"):
            self.service.book(DONOR, first["id"], slot["id"], False)
        receipt = self.service.book(DONOR, first["id"], slot["id"], True)
        self.assertEqual(receipt["date"], self.day.isoformat())
        with self.assertRaises(ValueError):
            self.service.book(OTHER_DONOR, second["id"], slot["id"], True)

    def test_invalid_quantity_rejected(self):
        with self.assertRaises(ValueError):
            self.service.submit_offer(DONOR, {"Rice": 0})

    def test_priority_categories_visible_to_donor(self):
        self.service.set_priorities(STAFF, ["Rice", " Vegetables "])
        self.assertEqual(self.service.priorities(DONOR), ["Rice", "Vegetables"])


if __name__ == "__main__":
    unittest.main()
