"""Food safety checks for a proposed hamper item."""

from datetime import date


def item_is_safe(profile, item):
    if item["quantity"] <= 0 or date.fromisoformat(item["expiry_date"]) < date.today():
        return False
    allergies = set(profile.get("allergies", [])) - {"None"}
    if allergies & (set(item.get("allergen_tags", [])) - {"None"}):
        return False
    requirements = (set(profile.get("dietary_requirements", [])) |
                    set(profile.get("cultural_requirements", []))) - {"None"}
    return requirements <= set(item.get("dietary_tags", []))
