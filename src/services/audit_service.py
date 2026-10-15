"""Append and read access events."""

from src.domain.access_log import new_entry


class AuditService:
    def __init__(self, repository):
        self.repository = repository

    def record(self, actor_id, action, target_id):
        entry = new_entry(actor_id, action, target_id)
        self.repository.update("access_log", lambda rows: rows.append(entry))
        return entry

    def list_entries(self, actor):
        if actor["role"] != "Admin":
            raise PermissionError("Access log is restricted to admins")
        return list(reversed(self.repository.read("access_log")))
