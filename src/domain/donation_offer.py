"""Donation offer input rules."""


def validate_offer(items):
    if not items:
        raise ValueError("Add at least one item category")
    for category, quantity in items.items():
        if not str(category).strip() or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("Each category needs a quantity greater than zero")
