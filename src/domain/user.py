"""User roles and public account fields."""

ROLES = ("Staff", "Volunteer", "Donor", "Client", "Admin")


def public_user(user):
    """Account fields that may leave the service layer; password_hash is deliberately excluded."""
    return {key: user[key] for key in ("id", "username", "role", "active")}
