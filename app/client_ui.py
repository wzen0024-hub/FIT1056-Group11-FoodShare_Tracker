"""Client and staff profile screens."""

import streamlit as st

from src.domain.client_profile import COMMUNICATION_METHODS, NO_COMMUNICATION_PREFERENCE


ALLERGENS = ["None", "Peanut", "Tree nut", "Dairy", "Egg", "Gluten", "Soy", "Fish"]
SUITABILITY = ["None", "Vegetarian", "Vegan", "Halal", "Kosher", "Gluten-free"]


def _requirement_name(value):
    """Show the stored value "None" as "No restrictions" (FR-01.7); the stored data is unchanged."""
    return "No restrictions" if value == "None" else value


# Each label explains why the information is collected (FR-01.8). The tests import
# these names, so change the text here and nowhere else.
ACCESSIBILITY_LABEL = "Accessibility needs — needed to arrange suitable support (optional)"
COMMUNICATION_LABEL = ("Preferred communication method — kept for staff reference only; "
                       "the system does not send messages")


def render(actor, profiles, auth):
    st.header("Client profiles" if actor["role"] == "Staff" else "My profile")
    if actor["role"] == "Staff":
        clients = profiles.list_clients(actor)
        if not clients:
            st.info("Ask an admin to create a Client account first.")
            return
        client = st.selectbox("Client account", clients, format_func=lambda c: c["username"])
        client_id = client["id"]
    else:
        client_id = actor["id"]
    existing = profiles.get_profile(actor, client_id) or {}
    stored_method = existing.get("preferred_communication", NO_COMMUNICATION_PREFERENCE)
    # The form key contains the client id. A staff member can switch client without
    # submitting; a form per client stops one client's unsaved entries from appearing
    # under (and being saved to) another client when both profiles share the same defaults.
    with st.form(f"profile_form_{client_id}"):
        household_size = st.number_input("Household size — needed to plan food quantity", min_value=1,
                                          value=existing.get("household_size", 1), step=1)
        dietary = st.multiselect("Dietary requirements — needed to choose suitable food",
                                 SUITABILITY, default=existing.get("dietary_requirements", ["None"]),
                                 format_func=_requirement_name)
        allergies = st.multiselect("Allergies — needed to prevent unsafe food",
                                   ALLERGENS, default=existing.get("allergies", ["None"]))
        cultural = st.multiselect("Cultural or religious food needs — needed for a respectful hamper",
                                  SUITABILITY, default=existing.get("cultural_requirements", ["None"]),
                                  format_func=_requirement_name)
        accessibility = st.text_area(ACCESSIBILITY_LABEL, value=existing.get("accessibility_needs", ""))
        communication = st.selectbox(
            COMMUNICATION_LABEL, COMMUNICATION_METHODS,
            index=COMMUNICATION_METHODS.index(stored_method) if stored_method in COMMUNICATION_METHODS else 0)
        note = ""
        if actor["role"] == "Staff":
            note = st.text_area("Staff-only substitution note", value=existing.get("substitution_note", ""))
        consent = st.checkbox("I confirm consent to store this sensitive profile",
                              value=existing.get("consent", False))
        saved = st.form_submit_button("Save profile")
    if saved:
        try:
            profiles.save_profile(actor, client_id, household_size=int(household_size),
                                  dietary_requirements=dietary, allergies=allergies,
                                  cultural_requirements=cultural, consent=consent,
                                  substitution_note=note, accessibility_needs=accessibility,
                                  preferred_communication=communication)
            st.success("Profile saved")
        except (ValueError, PermissionError) as error:
            st.error(str(error))

    if actor["role"] == "Client" and existing:
        st.subheader("Delete my profile")
        confirmed = st.checkbox("I confirm I want to delete my profile")
        if st.button("Delete profile"):
            try:
                profiles.delete_own_profile(actor, confirmed)
                st.success("Profile deleted")
                st.rerun()
            except ValueError as error:
                st.error(str(error))
