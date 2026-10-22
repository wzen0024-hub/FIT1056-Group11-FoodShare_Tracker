"""Donation offer input rules (FR-04.1)."""


def _normalise_pairs(pairs):
    """Validate (category, quantity) pairs and return a clean {category: quantity} dict.

    Pairs are checked one by one instead of building a dict first, because a dict would
    silently overwrite the quantity of a repeated category.
    """
    cleaned, seen = {}, set()
    for category, quantity in pairs:
        if not isinstance(category, str):
            raise ValueError("Every item category needs a name")
        name = " ".join(category.split())  # trim and collapse repeated spaces
        if not name:
            raise ValueError("Every item category needs a name")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise ValueError(f"Quantity for '{name}' must be a whole number greater than zero")
        if name.casefold() in seen:
            raise ValueError(f"'{name}' is listed more than once; combine it into one line")
        seen.add(name.casefold())
        cleaned[name] = quantity
    if not cleaned:
        raise ValueError("Add at least one item category")
    return cleaned


def normalise_offer(items):
    """Validate an offer given as {category: quantity} and return the cleaned dict."""
    if not isinstance(items, dict):
        raise ValueError("Add at least one item category")
    return _normalise_pairs(items.items())


def validate_offer(items):
    """Raise ValueError when the offer is not acceptable (kept for existing callers)."""
    normalise_offer(items)


def offer_from_rows(rows):
    """Build an offer from form rows of (category, quantity).

    A row that is completely unused (blank category and a zero/missing quantity) is
    skipped so a donor can leave spare rows empty. A half-filled row is NOT skipped,
    so a missing category or a zero quantity is reported instead of being ignored.
    """
    used = [(category, quantity) for category, quantity in rows
            if (isinstance(category, str) and category.strip()) or quantity]
    return _normalise_pairs(used)
