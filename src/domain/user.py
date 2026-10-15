"""User roles and public account fields."""

ROLES = ("Staff", "Volunteer", "Donor", "Client", "Admin")


def public_user(user):
    return {key: user[key] for key in ("id", "username", "role", "active")}
