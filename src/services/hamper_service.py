"""Safe hamper creation and packing."""

from datetime import date
from uuid import uuid4

from src.domain.hamper import find_conflicts, item_is_safe
from src.services.auth_service import require_role


# Shown to every role. It must never say WHY an item conflicts (FR-03.7).
CANNOT_ADD = "Warning: item cannot be added to this hamper"


def _volunteer_lines(items):
    """Volunteer-safe hamper lines: item name and quantity only (FR-03.6).

    Internal ids stay inside the service layer; the Packing View does not need them.
    """
    return [{"name": line["name"], "quantity": line["quantity"]} for line in items]


def _staff_conflict_message(conflicts):
    """Specific warning for authorised staff only (FR-03.7, AC-33)."""
    reasons = []
    if conflicts["allergies"]:
        reasons.append("it conflicts with the client's allergy: " + ", ".join(conflicts["allergies"]))
    if conflicts["requirements"]:
        reasons.append("it is not tagged for the client's dietary or cultural requirement: "
                       + ", ".join(conflicts["requirements"]))
    if conflicts["unavailable"]:
        reasons.append("it is " + " and ".join(conflicts["unavailable"]))
    return f"{CANNOT_ADD}: " + "; ".join(reasons)


class HamperService:
    def __init__(self, repository, profile_service):
        self.repository = repository
        self.profiles = profile_service

    def generate(self, actor, client_id):
        require_role(actor, "Staff")
        profile = self.profiles.get_profile(actor, client_id)
        if profile is None:
            raise ValueError("Client profile not found")
        eligible = [item for item in self.repository.read("inventory") if item_is_safe(profile, item)]
        if not eligible:
            raise ValueError("No suitable food is available for this client")
        eligible.sort(key=lambda item: item["expiry_date"])
        hamper = {"id": str(uuid4()), "client_id": client_id, "status": "Pending",
                  "created_on": date.today().isoformat(),
                  "items": [{"item_id": item["id"], "name": item["name"], "quantity": 1}
                            for item in eligible]}
        self.repository.update("hampers", lambda rows: rows.append(hamper))
        return hamper

    def pending_for_packing(self, actor):
        require_role(actor, "Staff", "Volunteer")
        rows = [h for h in self.repository.read("hampers") if h["status"] == "Pending"]
        if actor["role"] == "Volunteer":
            return [{"id": h["id"], "items": _volunteer_lines(h["items"])} for h in rows]
        return rows

    def add_item(self, actor, hamper_id, item_id):
        """Manually add one unit of an item to a pending hamper (FR-03.2, FR-03.7).

        Unsafe items are always blocked. The error text depends on the role: staff
        learn which allergy or requirement conflicts, volunteers only that the item
        cannot be added.
        """
        require_role(actor, "Staff", "Volunteer")
        is_staff = actor["role"] == "Staff"
        with self.repository.lock:
            hampers = self.repository.read("hampers")
            hamper = next((h for h in hampers if h["id"] == hamper_id), None)
            if hamper is None or hamper["status"] != "Pending":
                raise ValueError("Pending hamper not found")
            # Volunteers cannot read profiles, so the service reads the profile on their
            # behalf. The result is used for the safety check only and is never returned.
            staff = {"id": actor["id"], "role": "Staff"}
            profile = self.profiles.get_profile(staff, hamper["client_id"])
            item = next((i for i in self.repository.read("inventory") if i["id"] == item_id), None)
            if profile is None or item is None:
                raise ValueError(CANNOT_ADD)
            conflicts = find_conflicts(profile, item)
            if any(conflicts.values()):
                raise ValueError(_staff_conflict_message(conflicts) if is_staff else CANNOT_ADD)
            current = next((line for line in hamper["items"] if line["item_id"] == item_id), None)
            if current:
                if current["quantity"] >= item["quantity"]:
                    # Stock levels are not client data, so staff may be told the reason.
                    raise ValueError(
                        f"{CANNOT_ADD}: all {item['quantity']} units in stock are already in this hamper"
                        if is_staff else CANNOT_ADD)
                current["quantity"] += 1
            else:
                hamper["items"].append({"item_id": item_id, "name": item["name"], "quantity": 1})
            self.repository.write("hampers", hampers)
            if is_staff:
                return hamper
            return {"id": hamper["id"], "items": _volunteer_lines(hamper["items"])}

    def mark_packed(self, actor, hamper_id):
        require_role(actor, "Staff", "Volunteer")
        with self.repository.lock:
            hampers = self.repository.read("hampers")
            hamper = next((h for h in hampers if h["id"] == hamper_id), None)
            if hamper is None or hamper["status"] != "Pending":
                raise ValueError("Pending hamper not found")
            inventory = self.repository.read("inventory")
            by_id = {item["id"]: item for item in inventory}
            staff = {"id": actor["id"], "role": "Staff"}
            profile = self.profiles.get_profile(staff, hamper["client_id"])
            for line in hamper["items"]:
                item = by_id.get(line["item_id"])
                if profile is None or item is None or not item_is_safe(profile, item):
                    raise ValueError("Warning: hamper must be reviewed before packing")
                if item["quantity"] < line["quantity"]:
                    raise ValueError("Insufficient stock; nothing was packed")
            original = self.repository.read("inventory")
            for line in hamper["items"]:
                by_id[line["item_id"]]["quantity"] -= line["quantity"]
            self.repository.write("inventory", inventory)
            try:
                hamper["status"] = "Packed"
                self.repository.write("hampers", hampers)
            except Exception:
                self.repository.write("inventory", original)
                raise
            return {"id": hamper["id"], "status": "Packed"}

    def client_history(self, actor, client_id):
        require_role(actor, "Staff")
        return [h for h in self.repository.read("hampers") if h["client_id"] == client_id]
