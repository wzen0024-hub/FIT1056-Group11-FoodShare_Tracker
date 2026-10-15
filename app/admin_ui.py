"""Administrator account management and audit view."""

import streamlit as st

from src.domain.user import ROLES


def render(actor, auth, audit):
    st.header("User administration")
    with st.form("new_user"):
        username = st.text_input("New username")
        password = st.text_input("New password (8+ characters)", type="password")
        role = st.selectbox("Role", ROLES)
        submitted = st.form_submit_button("Create user")
    if submitted:
        try:
            auth.create_user(actor, username, password, role)
            st.success("Account created")
        except (ValueError, PermissionError) as error:
            st.error(str(error))

    users = auth.list_users(actor)
    st.dataframe(users, hide_index=True)
    editable = [u for u in users if u["role"] != "Admin" or u["id"] == actor["id"]]
    with st.form("change_user"):
        target = st.selectbox("Account to update", editable,
                              format_func=lambda u: f"{u['username']} ({u['role']})")
        new_role = st.selectbox("New role", ROLES, index=ROLES.index(target["role"]))
        active = st.checkbox("Account active", value=target["active"])
        changed = st.form_submit_button("Save account")
    if changed:
        try:
            auth.change_user(actor, target["id"], role=new_role, active=active)
            st.success("Account updated. New role applies at next login.")
        except (ValueError, PermissionError) as error:
            st.error(str(error))
    st.subheader("Access log")
    st.dataframe(audit.list_entries(actor), hide_index=True)
