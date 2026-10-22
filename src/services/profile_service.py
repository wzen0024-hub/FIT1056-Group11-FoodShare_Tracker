"""Client profile access, consent and validation."""

from uuid import uuid4

from src.domain.client_profile import (NO_COMMUNICATION_PREFERENCE, PROFILE_DEFAULTS,
                                       validate_profile, with_profile_defaults)
from src.services.auth_service import require_role


class ProfileService:
    def __init__(self, repository, audit):
        self.repository = repository
        self.audit = audit

    def save_profile(self, actor, client_id, *, household_size, dietary_requirements,
                     allergies, cultural_requirements, consent, substitution_note="",
                     accessibility_needs=None, preferred_communication=None):
        """Create or update a client profile (FR-01.1, FR-01.2, FR-01.6).

        Staff may save any client's profile; a Client may save only their own.
        accessibility_needs and preferred_communication default to None, which means
        "leave the stored value unchanged" (or use the default for a new profile). This
        keeps older callers that do not pass them from erasing data by accident.
        """
        require_role(actor, "Staff", "Client")
        if actor["role"] == "Client" and actor["id"] != client_id:
            raise PermissionError("Clients may edit only their own profile")
        validate_profile(household_size, dietary_requirements, consent,
                         "" if accessibility_needs is None else accessibility_needs,
                         NO_COMMUNICATION_PREFERENCE if preferred_communication is None
                         else preferred_communication)
        if not isinstance(allergies, list) or not isinstance(cultural_requirements, list):
            raise ValueError("Allergies and cultural requirements must be lists")

        def save(profiles):
            profile = next((p for p in profiles if p["client_id"] == client_id), None)
            if profile is None:
                profile = {"id": str(uuid4()), "client_id": client_id, "substitution_note": ""}
                profiles.append(profile)
            profile.update({"household_size": household_size,
                            "dietary_requirements": dietary_requirements,
                            "allergies": allergies,
                            "cultural_requirements": cultural_requirements,
                            "consent": True})
            if accessibility_needs is not None:
                profile["accessibility_needs"] = accessibility_needs.strip()
            if preferred_communication is not None:
                profile["preferred_communication"] = preferred_communication
            for field, default in PROFILE_DEFAULTS.items():
                profile.setdefault(field, default)  # upgrade records saved before these fields
            # The substitution note is staff-only (FR-01.3): a client save never touches it.
            if actor["role"] == "Staff":
                profile["substitution_note"] = substitution_note.strip()
            return dict(profile)

        result = self.repository.update("profiles", save)
        self.audit.record(actor["id"], "profile_saved", client_id)
        return result if actor["role"] == "Staff" else self._client_view(result)

    @staticmethod
    def _client_view(profile):
        """Hide staff-only fields from the client."""
        return {key: value for key, value in profile.items() if key != "substitution_note"}

    def get_profile(self, actor, client_id):
        require_role(actor, "Staff", "Client")
        if actor["role"] == "Client" and actor["id"] != client_id:
            raise PermissionError("Clients may view only their own profile")
        profile = next((p for p in self.repository.read("profiles") if p["client_id"] == client_id), None)
        if profile is None:
            return None
        profile = with_profile_defaults(profile)
        return profile if actor["role"] == "Staff" else self._client_view(profile)

    def list_profiles(self, actor):
        require_role(actor, "Staff")
        return [with_profile_defaults(profile) for profile in self.repository.read("profiles")]

    def list_clients(self, actor):
        require_role(actor, "Staff")
        return [{"id": user["id"], "username": user["username"]}
                for user in self.repository.read("users")
                if user["role"] == "Client" and user["active"]]

    def delete_own_profile(self, actor, confirmed):
        """Delete the Client's own profile (FR-01.5) and log it without personal data (FR-05.7)."""
        require_role(actor, "Client")
        if not confirmed:
            raise ValueError("Confirm deletion first")

        def delete(profiles):
            before = len(profiles)
            profiles[:] = [p for p in profiles if p["client_id"] != actor["id"]]
            return len(profiles) < before

        if not self.repository.update("profiles", delete):
            # Nothing was removed, so nothing may be written to the audit trail.
            raise ValueError("There is no profile to delete")
        # The entry holds only ids and the action name, never the deleted profile contents.
        self.audit.record(actor["id"], "profile_deleted", actor["id"])
