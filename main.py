"""Streamlit entry point for the FoodShare Tracker MVP."""

import streamlit as st

from app import admin_ui, auth_ui, client_ui, donor_ui, hamper_ui, inverntory_ui
from src.data.json_repository import JsonRepository
from src.services.audit_service import AuditService
from src.services.auth_service import AuthService
from src.services.donation_service import DonationService
from src.services.hamper_service import HamperService
from src.services.inventory_service import InventoryService
from src.services.profile_service import ProfileService


@st.cache_resource
def services():
    """Build the repository and services once per server process, shared by all sessions.

    The data folder is fixed when this first runs (see JsonRepository for how it is
    chosen), so a changed FOODSHARE_DATA_DIR needs a server restart. Tests call
    st.cache_resource.clear() so that each test gets its own temporary folder.
    """
    repository = JsonRepository()
    audit = AuditService(repository)
    profile = ProfileService(repository, audit)
    return {"auth": AuthService(repository, audit), "audit": audit,
            "profiles": profile, "inventory": InventoryService(repository),
            "hampers": HamperService(repository, profile),
            "donations": DonationService(repository)}


def main():
    st.set_page_config(page_title="FoodShare Tracker", layout="wide")
    st.title("FoodShare Tracker")
    api = services()
    if "user" not in st.session_state:
        st.session_state.user = None
    if st.session_state.user is None:
        auth_ui.render(api["auth"])
        return

    actor = st.session_state.user
    st.sidebar.write(f"Signed in: **{actor['username']}** ({actor['role']})")
    if st.sidebar.button("Log out"):
        # Clear everything, not just "user", so no form state, flash message or
        # remembered selection can appear for the next person on this browser (FR-05.11).
        st.session_state.clear()
        st.session_state.user = None
        st.rerun()

    pages = {
        "Staff": ["Client profiles", "Inventory", "Safe hampers", "Donor setup"],
        "Volunteer": ["Packing view", "Inventory"],
        "Donor": ["Donation offers"],
        "Client": ["My profile"],
        "Admin": ["User administration", "Inventory"],
    }
    page = st.sidebar.radio("Page", pages[actor["role"]])
    if page in {"Client profiles", "My profile"}:
        client_ui.render(actor, api["profiles"], api["auth"])
    elif page == "Inventory":
        inverntory_ui.render(actor, api["inventory"])
    elif page in {"Safe hampers", "Packing view"}:
        hamper_ui.render(actor, api["hampers"], api["profiles"], api["inventory"])
    elif page in {"Donor setup", "Donation offers"}:
        donor_ui.render(actor, api["donations"])
    elif page == "User administration":
        admin_ui.render(actor, api["auth"], api["audit"])


if __name__ == "__main__":
    main()
