"""Stock intake, display and issue reports."""

from uuid import uuid4

from src.domain.inventory_item import expires_soon, validate_item
from src.services.auth_service import require_role


class InventoryService:
    def __init__(self, repository):
        self.repository = repository

    def add_item(self, actor, *, name, category, quantity, expiry_date,
                 allergen_tags, dietary_tags):
        require_role(actor, "Staff")
        if not name.strip() or not category.strip():
            raise ValueError("Name and category are required")
        validate_item(quantity, expiry_date, allergen_tags, dietary_tags)
        item = {"id": str(uuid4()), "name": name.strip(), "category": category.strip(),
                "quantity": quantity, "expiry_date": str(expiry_date),
                # dict.fromkeys drops repeated tags while keeping the selection order
                "allergen_tags": list(dict.fromkeys(allergen_tags)),
                "dietary_tags": list(dict.fromkeys(dietary_tags)),
                "issues": []}
        self.repository.update("inventory", lambda rows: rows.append(item))
        return item

    def list_items(self, actor):
        """Inventory sorted by expiry (FR-02.2), including each item's saved issue flags (FR-02.7)."""
        require_role(actor, "Staff", "Volunteer", "Admin")
        return [{**item, "expires_soon": expires_soon(item["expiry_date"]),
                 "issues": item.get("issues", [])}  # records saved before flags existed
                for item in sorted(self.repository.read("inventory"),
                                   key=lambda x: x["expiry_date"])]

    def flag_issue(self, actor, item_id, reason, comment):
        """Attach an issue (reason + comment) to an item so the inventory list can show it (FR-02.7).

        Only Staff and Volunteers may flag (Table 17). Flags accumulate in item["issues"];
        reported_by stores a user id for traceability and is not shown on the inventory list.
        """
        require_role(actor, "Staff", "Volunteer")
        if reason not in {"Damaged", "Spoiled", "Incorrect count"} or not (comment or "").strip():
            raise ValueError("Select a reason and write a comment")

        def flag(rows):
            item = next((row for row in rows if row["id"] == item_id), None)
            if item is None:
                raise ValueError("Item not found")
            item.setdefault("issues", []).append({"reason": reason, "comment": comment.strip(),
                                                    "reported_by": actor["id"]})
            return item

        return self.repository.update("inventory", flag)
