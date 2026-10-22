"""Authentication and account administration."""

import hashlib
import hmac
import secrets
from uuid import uuid4

from src.domain.user import ROLES, public_user


def require_role(actor, *roles):
    """Raise PermissionError unless `actor` (the signed-in user dict) has one of `roles`.

    Service methods that are restricted by role start with this check, so permissions
    are enforced here and not only by the menu in main.py.
    """
    if not actor or actor.get("role") not in roles:
        raise PermissionError("This action is not permitted for your role")


def _hash_password(password, salt=None):
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters")
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000)
    return f"pbkdf2_sha256$200000${salt}${digest.hex()}"


def _verify_password(password, encoded):
    try:
        method, rounds, salt, expected = encoded.split("$")
        if method != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, AttributeError):
        return False


class AuthService:
    def __init__(self, repository, audit):
        self.repository = repository
        self.audit = audit

    def has_users(self):
        return bool(self.repository.read("users"))

    def bootstrap_admin(self, username, password):
        if self.has_users():
            raise PermissionError("Initial admin has already been created")
        return self._create(None, username, password, "Admin")

    def _create(self, actor, username, password, role):
        if role not in ROLES:
            raise ValueError("Invalid role")
        username = username.strip()
        if not username:
            raise ValueError("Username is required")
        password_hash = _hash_password(password)

        def add(users):
            if any(user["username"].casefold() == username.casefold() for user in users):
                raise ValueError("Username already exists")
            user = {"id": str(uuid4()), "username": username, "role": role,
                    "password_hash": password_hash, "active": True}
            users.append(user)
            return public_user(user)

        created = self.repository.update("users", add)
        self.audit.record(actor["id"] if actor else created["id"], "user_created", created["id"])
        return created

    def create_user(self, actor, username, password, role):
        require_role(actor, "Admin")
        return self._create(actor, username, password, role)

    def authenticate(self, username, password):
        for user in self.repository.read("users"):
            if user["active"] and user["username"].casefold() == username.strip().casefold():
                if _verify_password(password, user["password_hash"]):
                    return public_user(user)
        raise ValueError("Invalid username or password")

    def list_users(self, actor):
        require_role(actor, "Admin")
        return [public_user(user) for user in self.repository.read("users")]

    def editable_users(self, actor):
        """Accounts this Admin may modify: every non-Admin account plus the Admin's own.

        Another Admin's account is excluded (FR-05.5). change_user() enforces the same
        rule, so the account selector in the UI and the service always agree.
        """
        return [user for user in self.list_users(actor)
                if user["role"] != "Admin" or user["id"] == actor["id"]]

    def change_user(self, actor, user_id, *, role=None, active=None):
        """Change an account's role and/or active flag (FR-05.4); only Admins may call this.

        Another Admin's account cannot be modified (FR-05.5), and an Admin cannot remove
        their own access. A changed role is stored immediately, but it only affects the
        user at their next login because the session keeps the role copied at sign-in
        (FR-05.6). Role and enable/disable changes are written to the access log (FR-05.3).
        """
        require_role(actor, "Admin")
        if role is not None and role not in ROLES:
            raise ValueError("Invalid role")

        def change(users):
            user = next((u for u in users if u["id"] == user_id), None)
            if user is None:
                raise ValueError("User not found")
            if user["role"] == "Admin" and user["id"] != actor["id"]:
                raise PermissionError("Another admin account cannot be modified")
            if user["id"] == actor["id"] and (role not in (None, "Admin") or active is False):
                raise PermissionError("The current admin cannot remove their own access")
            old_role, old_active = user["role"], user["active"]
            if role is not None:
                user["role"] = role
            if active is not None:
                user["active"] = bool(active)
            return public_user(user), old_role, old_active

        updated, old_role, old_active = self.repository.update("users", change)
        if role is not None and role != old_role:
            self.audit.record(actor["id"], "role_changed", user_id)
        if active is not None and active != old_active:
            self.audit.record(actor["id"], "user_disabled" if not active else "user_enabled", user_id)
        return updated
