"""Multi-category offers (FR-04.1, AC-35-37) and date-specific drop-off slots (FR-04.4/04.5, AC-40/41).

Every test uses a temporary data folder; the real data/*.json files are never touched.
"""

import tempfile
import unittest
from datetime import date, datetime, timedelta

from src.data.json_repository import JsonRepository
from src.domain.donation_offer import offer_from_rows
from src.services.donation_service import DonationService


STAFF = {"id": "staff-1", "role": "Staff"}
DONOR = {"id": "donor-1", "role": "Donor"}
OTHER_DONOR = {"id": "donor-2", "role": "Donor"}
CLIENT = {"id": "client-1", "role": "Client"}


class OfferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = JsonRepository(self.temp.name)
        self.service = DonationService(self.repo)

    def tearDown(self):
        self.temp.cleanup()

    def test_offer_with_several_categories_is_saved_in_pending_arrivals(self):
        offer = self.service.submit_offer(DONOR, {" Rice ": 3, "Fruit": 2, "Tinned  beans": 10})
        self.assertEqual(offer["items"], {"Rice": 3, "Fruit": 2, "Tinned beans": 10})
        self.assertEqual(self.repo.read("donations")["offers"][0]["items"], offer["items"])
        self.assertEqual(self.service.own_offers(DONOR)[0]["id"], offer["id"])

    def test_invalid_offers_are_rejected_and_nothing_is_saved(self):
        bad_offers = ({}, None, {"": 2}, {"   ": 2}, {"Rice": 0}, {"Rice": -1}, {"Rice": True},
                      {"Rice": 1.5}, {"Rice": "3"}, {"Rice": 2, "rice": 3}, {"Rice": 2, " RICE ": 3},
                      {"Rice": 2, "Fruit": 0})
        for items in bad_offers:
            with self.subTest(items=items), self.assertRaises(ValueError):
                self.service.submit_offer(DONOR, items)
        self.assertEqual(self.repo.read("donations"), {})

    def test_only_donors_can_submit_offers(self):
        for actor in (STAFF, CLIENT, None):
            with self.assertRaises(PermissionError):
                self.service.submit_offer(actor, {"Rice": 1})

    def test_offer_from_rows_skips_unused_rows_but_reports_half_filled_ones(self):
        self.assertEqual(offer_from_rows([("Rice", 3), ("", 0), ("  ", 0), ("Fruit", 2)]),
                         {"Rice": 3, "Fruit": 2})
        for rows in ([("", 0)], [("Rice", 0)], [("", 4)], [("Rice", 1), ("rice", 2)], [("Rice", -2)]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                offer_from_rows(rows)

    def test_a_multi_category_offer_can_be_booked(self):
        slot = self.service.define_slot(STAFF, date.today() + timedelta(days=1), "10:00")
        offer = self.service.submit_offer(DONOR, {"Rice": 3, "Fruit": 2})
        receipt = self.service.book(DONOR, offer["id"], slot["id"], True)
        self.assertEqual(receipt["start_time"], "10:00")
        self.assertEqual(self.service.own_offers(DONOR)[0]["slot_id"], slot["id"])


class SlotDateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = JsonRepository(self.temp.name)
        self.service = DonationService(self.repo)
        self.day1 = date.today() + timedelta(days=1)
        self.day2 = date.today() + timedelta(days=3)
        self.empty_day = date.today() + timedelta(days=2)

    def tearDown(self):
        self.temp.cleanup()

    def test_only_slots_on_the_selected_date_are_listed_in_time_order(self):
        self.service.define_slot(STAFF, self.day1, "14:00")
        self.service.define_slot(STAFF, self.day1, "09:00")
        self.service.define_slot(STAFF, self.day2, "11:00")
        times = [s["start_time"] for s in self.service.available_slots(DONOR, self.day1)]
        self.assertEqual(times, ["09:00", "14:00"])
        self.assertEqual([s["date"] for s in self.service.available_slots(DONOR, self.day2)],
                         [self.day2.isoformat()])
        self.assertEqual(self.service.available_dates(DONOR), [self.day1.isoformat(), self.day2.isoformat()])

    def test_date_without_slots_returns_an_empty_list(self):
        self.service.define_slot(STAFF, self.day1, "09:00")
        self.assertEqual(self.service.available_slots(DONOR, self.empty_day), [])
        self.assertNotIn(self.empty_day.isoformat(), self.service.available_dates(DONOR))

    def test_no_slots_anywhere_gives_no_dates(self):
        self.assertEqual(self.service.available_dates(DONOR), [])
        self.assertEqual(self.service.available_slots(DONOR), [])

    def test_booked_slot_disappears_for_every_donor_and_cannot_be_double_booked(self):
        slot = self.service.define_slot(STAFF, self.day1, "09:00")
        self.service.define_slot(STAFF, self.day1, "10:00")
        first = self.service.submit_offer(DONOR, {"Rice": 1})
        second = self.service.submit_offer(OTHER_DONOR, {"Fruit": 1})
        self.service.book(DONOR, first["id"], slot["id"], True)
        times = [s["start_time"] for s in self.service.available_slots(OTHER_DONOR, self.day1)]
        self.assertEqual(times, ["10:00"])
        with self.assertRaisesRegex(ValueError, "another available"):
            self.service.book(OTHER_DONOR, second["id"], slot["id"], True)
        self.assertEqual(self.service.available_dates(OTHER_DONOR), [self.day1.isoformat()])

    def test_fully_booked_date_drops_out_of_available_dates(self):
        slot = self.service.define_slot(STAFF, self.day1, "09:00")
        offer = self.service.submit_offer(DONOR, {"Rice": 1})
        self.service.book(DONOR, offer["id"], slot["id"], True)
        self.assertEqual(self.service.available_dates(DONOR), [])

    def test_past_slots_are_never_offered(self):
        past = (datetime.now() - timedelta(hours=1))
        self.repo.write("donations", {"slots": [{"id": "old", "date": past.date().isoformat(),
                                                  "start_time": past.strftime("%H:%M"), "offer_id": None}]})
        self.assertEqual(self.service.available_slots(DONOR), [])
        self.assertEqual(self.service.available_dates(DONOR), [])

    def test_checklist_is_still_required(self):
        slot = self.service.define_slot(STAFF, self.day1, "09:00")
        offer = self.service.submit_offer(DONOR, {"Rice": 1})
        with self.assertRaisesRegex(ValueError, "checklist"):
            self.service.book(DONOR, offer["id"], slot["id"], False)
        self.assertEqual(len(self.service.available_slots(DONOR, self.day1)), 1)


if __name__ == "__main__":
    unittest.main()
