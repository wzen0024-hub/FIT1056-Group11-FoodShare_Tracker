"""Inventory validation and expiry rules."""

from datetime import date

# FR-02.6: every item needs allergen and dietary tags, or the explicit "None" tag.
NO_TAG = "None"


def validate_tag_selection(tags, description):
    """Require at least one tag, and never "None" together with a real tag.

    "None" means "this item has no allergens / no dietary suitability tags", so
    combining it with a real tag would contradict itself.
    """
    if not isinstance(tags, (list, tuple, set)) or not tags:
        raise ValueError(f"Select at least one {description} tag, or None")
    if NO_TAG in tags and len(set(tags)) > 1:
        raise ValueError(f"{description.capitalize()} tags: choose either None or specific tags, not both")


def validate_item(quantity, expiry_date, allergen_tags, dietary_tags):
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
        raise ValueError("Quantity must be greater than zero")
    if date.fromisoformat(str(expiry_date)) < date.today():
        raise ValueError("Expired food cannot enter active inventory")
    validate_tag_selection(allergen_tags, "allergen")
    validate_tag_selection(dietary_tags, "dietary suitability")


def expires_soon(expiry_date):
    """True when the item expires today or within the next 2 calendar days (FR-02.2).

    Expiry dates carry no time of day, so "within 48 hours" is applied as 0-2 days ahead.
    Items that are already past their date return False; hamper matching excludes them.
    """
    return 0 <= (date.fromisoformat(expiry_date) - date.today()).days <= 2
