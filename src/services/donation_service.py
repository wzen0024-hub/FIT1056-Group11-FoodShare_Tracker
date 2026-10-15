"""Donation offers, safety acknowledgement and drop-off slots."""

from datetime import date, datetime
from uuid import uuid4

from src.domain.donation_offer import validate_offer
from src.services.auth_service import require_role


class DonationService:
    def __init__(self, repository):
        self.repository = repository

    @staticmethod
    def _state(raw):
        return {"offers": raw.get("offers", []), "slots": raw.get("slots", []),
                "priority_categories": raw.get("priority_categories", [])}

    def priorities(self, actor):
        require_role(actor, "Staff", "Donor")
        return self._state(self.repository.read("donations"))["priority_categories"]

    def set_priorities(self, actor, categories):
        require_role(actor, "Staff")
        self.repository.update("donations", lambda raw: raw.update(
            self._state(raw) | {"priority_categories": sorted({x.strip() for x in categories if x.strip()})}))

    def define_slot(self, actor, day, start_time):
        require_role(actor, "Staff")
        when = datetime.fromisoformat(f"{day}T{start_time}")
        if when <= datetime.now():
            raise ValueError("Drop-off slot must be in the future")

        def add(raw):
            state = self._state(raw)
            if any(s["date"] == str(day) and s["start_time"] == start_time for s in state["slots"]):
                raise ValueError("Slot already exists")
            slot = {"id": str(uuid4()), "date": str(day), "start_time": start_time,
                    "offer_id": None}
            state["slots"].append(slot)
            raw.update(state)
            return slot

        return self.repository.update("donations", add)

    def available_slots(self, actor, day=None):
        require_role(actor, "Staff", "Donor")
        slots = self._state(self.repository.read("donations"))["slots"]
        return [s for s in slots if not s["offer_id"] and (day is None or s["date"] == str(day))
                and datetime.fromisoformat(f"{s['date']}T{s['start_time']}") > datetime.now()]

    def submit_offer(self, actor, items):
        require_role(actor, "Donor")
        validate_offer(items)
        offer = {"id": str(uuid4()), "donor_id": actor["id"], "items": items,
                 "checklist_acknowledged": False, "slot_id": None}

        def add(raw):
            state = self._state(raw)
            state["offers"].append(offer)
            raw.update(state)
        self.repository.update("donations", add)
        return offer

    def own_offers(self, actor):
        require_role(actor, "Donor")
        return [o for o in self._state(self.repository.read("donations"))["offers"]
                if o["donor_id"] == actor["id"]]

    def book(self, actor, offer_id, slot_id, checklist_acknowledged):
        require_role(actor, "Donor")
        if not checklist_acknowledged:
            raise ValueError("Acknowledge the food safety checklist before booking")

        def reserve(raw):
            state = self._state(raw)
            offer = next((o for o in state["offers"] if o["id"] == offer_id and o["donor_id"] == actor["id"]), None)
            slot = next((s for s in state["slots"] if s["id"] == slot_id), None)
            if offer is None or offer["slot_id"] is not None:
                raise ValueError("Open donation offer not found")
            if (slot is None or slot["offer_id"] or
                    datetime.fromisoformat(f"{slot['date']}T{slot['start_time']}") <= datetime.now()):
                raise ValueError("Choose another available date or slot")
            slot["offer_id"] = offer_id
            offer["slot_id"] = slot_id
            offer["checklist_acknowledged"] = True
            raw.update(state)
            return {"offer_id": offer_id, "date": slot["date"],
                    "start_time": slot["start_time"], "receipt_id": str(uuid4())}

        return self.repository.update("donations", reserve)
