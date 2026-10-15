"""Client and staff profile screens."""

import streamlit as st


ALLERGENS = ["None", "Peanut", "Tree nut", "Dairy", "Egg", "Gluten", "Soy", "Fish"]
SUITABILITY = ["None", "Vegetarian", "Vegan", "Halal", "Kosher", "Gluten-free"]


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
    with st.form("profile_form"):
        household_size = st.number_input("Household size — needed to plan food quantity", min_value=1,
                                          value=existing.get("household_size", 1), step=1)
        dietary = st.multiselect("Dietary requirements — needed to choose suitable food",
                                 SUITABILITY, default=existing.get("dietary_requirements", ["None"]))
        allergies = st.multiselect("Allergies — needed to prevent unsafe food",
                                   ALLERGENS, default=existing.get("allergies", ["None"]))
        cultural = st.multiselect("Cultural or religious food needs — needed for a respectful hamper",
                                  SUITABILITY, default=existing.get("cultural_requirements", ["None"]))
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
                                  substitution_note=note)
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
