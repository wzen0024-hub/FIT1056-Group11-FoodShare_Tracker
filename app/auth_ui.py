"""Login and first-run administrator setup."""

import streamlit as st


def render(auth):
    if not auth.has_users():
        st.info("Create the initial administrator account to start.")
        with st.form("bootstrap"):
            username = st.text_input("Admin username")
            password = st.text_input("Admin password (8+ characters)", type="password")
            submitted = st.form_submit_button("Create admin")
        if submitted:
            try:
                auth.bootstrap_admin(username, password)
                st.success("Admin created. Sign in below.")
            except (ValueError, PermissionError) as error:
                st.error(str(error))
    st.subheader("Sign in")
    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")
    if submitted:
        try:
            st.session_state.user = auth.authenticate(username, password)
            st.rerun()
        except ValueError as error:
            st.error(str(error))
