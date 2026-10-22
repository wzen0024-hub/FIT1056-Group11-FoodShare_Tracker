"""Login and first-run administrator setup."""

import streamlit as st


def render(auth):
    if not auth.has_users():
        st.info("Create the initial administrator account to start.")
        with st.form("bootstrap"):
            # A brand-new credential pair: "new-password" lets the browser offer to save
            # a new password for it.
            username = st.text_input("Admin username", autocomplete="username")
            password = st.text_input("Admin password (8+ characters)", type="password",
                                     autocomplete="new-password")
            submitted = st.form_submit_button("Create admin")
        if submitted:
            try:
                auth.bootstrap_admin(username, password)
                st.success("Admin created. Sign in below.")
            except (ValueError, PermissionError) as error:
                st.error(str(error))
    st.subheader("Sign in")
    with st.form("login"):
        # Streamlit gives every password input autocomplete="new-password" unless told
        # otherwise, which makes browsers suggest a strong NEW password on the sign-in
        # form. These two values mark the pair as an existing login, so browsers and
        # password managers offer the saved credentials instead.
        username = st.text_input("Username", autocomplete="username")
        password = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Sign in")
    if submitted:
        try:
            st.session_state.user = auth.authenticate(username, password)
            st.rerun()
        except ValueError as error:
            st.error(str(error))
