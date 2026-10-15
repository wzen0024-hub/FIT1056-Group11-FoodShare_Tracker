"""Client profile access, consent and validation."""

from uuid import uuid4

from src.domain.client_profile import validate_profile
from src.services.auth_service import require_role


class ProfileService:
    def __init__(self, repository, audit):
        self.repository = repository
        self.audit = audit

    def save_profile(self, actor, client_id, *, household_size, dietary_requirements,
                     allergies, cultural_requirements, consent, substitution_note=""):
        require_role(actor, "Staff", "Client")
        if actor["role"] == "Client" and actor["id"] != client_id:
            raise PermissionError("Clients may edit only their own profile")
        validate_profile(household_size, dietary_requirements, consent)
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
            if actor["role"] == "Staff":
                profile["substitution_note"] = substitution_note.strip()
            return dict(profile)

        result = self.repository.update("profiles", save)
        self.audit.record(actor["id"], "profile_saved", client_id)
        return result if actor["role"] == "Staff" else self._client_view(result)

    @staticmethod
    def _client_view(profile):
        return {key: value for key, value in profile.items() if key != "substitution_note"}

    def get_profile(self, actor, client_id):
        require_role(actor, "Staff", "Client")
        if actor["role"] == "Client" and actor["id"] != client_id:
            raise PermissionError("Clients may view only their own profile")
        profile = next((p for p in self.repository.read("profiles") if p["client_id"] == client_id), None)
        if profile is None:
            return None
        return profile if actor["role"] == "Staff" else self._client_view(profile)

    def list_profiles(self, actor):
        require_role(actor, "Staff")
        return self.repository.read("profiles")

    def list_clients(self, actor):
        require_role(actor, "Staff")
        return [{"id": user["id"], "username": user["username"]}
                for user in self.repository.read("users")
                if user["role"] == "Client" and user["active"]]

    def delete_own_profile(self, actor, confirmed):
        require_role(actor, "Client")
        if not confirmed:
            raise ValueError("Confirm deletion first")
        self.repository.update("profiles", lambda profiles: profiles.__setitem__(
            slice(None), [p for p in profiles if p["client_id"] != actor["id"]]))
        self.audit.record(actor["id"], "profile_deleted", actor["id"])
