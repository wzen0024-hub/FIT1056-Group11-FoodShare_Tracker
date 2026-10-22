"""Append and read access events."""

from src.domain.access_log import new_entry
from src.services.auth_service import require_role


class AuditService:
    def __init__(self, repository):
        self.repository = repository

    def record(self, actor_id, action, target_id):
        """Append one entry. Store ids and the action name only, never personal data (FR-05.7)."""
        entry = new_entry(actor_id, action, target_id)
        self.repository.update("access_log", lambda rows: rows.append(entry))
        return entry

    def list_entries(self, actor):
        # Same guard as the other services; it also rejects a missing actor (None) cleanly.
        require_role(actor, "Admin")
        return list(reversed(self.repository.read("access_log")))
