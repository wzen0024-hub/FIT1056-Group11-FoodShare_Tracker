"""Food safety checks for a proposed hamper item."""

from datetime import date


def find_conflicts(profile, item):
    """Explain why an item is not safe for a client's hamper.

    Returns a dict with three lists (all empty means the item is safe):
      "unavailable"  - the item is out of stock or expired (not client-specific)
      "allergies"    - the client's recorded allergies that match the item's allergen tags
      "requirements" - the client's dietary/cultural requirements the item is not tagged for

    The "allergies" and "requirements" lists are sensitive client data. Callers must
    only show them to authorised staff (FR-03.7), never to volunteers.
    """
    conflicts = {"unavailable": [], "allergies": [], "requirements": []}
    if item["quantity"] <= 0:
        conflicts["unavailable"].append("out of stock")
    if date.fromisoformat(item["expiry_date"]) < date.today():
        conflicts["unavailable"].append("expired")
    allergies = set(profile.get("allergies", [])) - {"None"}
    conflicts["allergies"] = sorted(allergies & (set(item.get("allergen_tags", [])) - {"None"}))
    requirements = (set(profile.get("dietary_requirements", [])) |
                    set(profile.get("cultural_requirements", []))) - {"None"}
    conflicts["requirements"] = sorted(requirements - set(item.get("dietary_tags", [])))
    return conflicts


def item_is_safe(profile, item):
    """True only when find_conflicts() reports nothing; the safety rule is unchanged."""
    return not any(find_conflicts(profile, item).values())
