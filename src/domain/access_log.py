"""Timestamped audit entries."""

from datetime import datetime, timezone
from uuid import uuid4


def new_entry(actor_id, action, target_id):
    return {"id": str(uuid4()), "actor_id": actor_id, "action": action,
            "target_id": target_id, "timestamp": datetime.now(timezone.utc).isoformat()}
