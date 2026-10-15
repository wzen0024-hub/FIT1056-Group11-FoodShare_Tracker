"""Inventory validation and expiry rules."""

from datetime import date


def validate_item(quantity, expiry_date, allergen_tags, dietary_tags):
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
        raise ValueError("Quantity must be greater than zero")
    if date.fromisoformat(str(expiry_date)) < date.today():
        raise ValueError("Expired food cannot enter active inventory")
    if not allergen_tags or not dietary_tags:
        raise ValueError("Select allergen and dietary tags, or None")


def expires_soon(expiry_date):
    return 0 <= (date.fromisoformat(expiry_date) - date.today()).days <= 2
