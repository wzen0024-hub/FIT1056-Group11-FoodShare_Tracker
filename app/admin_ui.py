"""Administrator account management and audit view."""

import streamlit as st

from src.domain.user import ROLES

FLASH_KEY = "admin_flash"          # one-off message shown after a deliberate st.rerun()
LAST_TARGET_KEY = "admin_last_target"  # id of the account that was saved last


def _label(user):
    return f"{user['username']} ({user['role']})"


def render(actor, auth, audit):
    st.header("User administration")
    message = st.session_state.pop(FLASH_KEY, None)
    if message:
        st.success(message)

    # --- Create a user -------------------------------------------------------------
    # clear_on_submit empties the fields (including the password) after every submit, so
    # pressing the button a second time cannot create a duplicate or hit "Username
    # already exists". If validation fails, the fields must be typed again.
    with st.form("new_user", clear_on_submit=True):
        # autocomplete="off": this is someone else's login, so the browser must not
        # fill it with the administrator's own saved credentials.
        username = st.text_input("New username", autocomplete="off")
        password = st.text_input("New password (8+ characters)", type="password",
                                 autocomplete="new-password")
        role = st.selectbox("Role", ROLES)
        submitted = st.form_submit_button("Create user")
    if submitted:
        try:
            created = auth.create_user(actor, username, password, role)
            st.success(f"Account created: {created['username']} ({created['role']})")
        except (ValueError, PermissionError) as error:
            st.error(str(error))

    # Read AFTER the create handler above so a new account is already in the list.
    users = auth.list_users(actor)        # public fields only: never password_hash
    st.dataframe(users, hide_index=True)

    # --- Update an existing user ---------------------------------------------------
    # The selector is OUTSIDE the form on purpose. Widgets inside st.form do not rerun
    # the script when they change, so the role selector and active checkbox below could
    # not follow a new selection. Outside the form, picking an account reruns the script
    # and the widgets below are rebuilt from that account.
    st.caption("Other administrator accounts appear in the table but cannot be modified (FR-05.5).")
    editable = {user["id"]: user for user in auth.editable_users(actor)}  # excludes other Admins
    ids = list(editable)
    # After a save the labels change (e.g. "khalid (Client)" -> "khalid (Staff)"), which
    # makes Streamlit treat the selector as a new widget. Start it on the account that
    # was just saved so the administrator does not jump back to the first account.
    last = st.session_state.get(LAST_TARGET_KEY)
    target_id = st.selectbox("Account to update", ids, index=ids.index(last) if last in ids else 0,
                             format_func=lambda user_id: _label(editable[user_id]))
    target = editable[target_id]
    with st.form("change_user"):
        # Each key contains the account id, so every account owns its widgets: an unsaved
        # choice made for one account can never appear on another. It also contains the
        # STORED role / active flag, so the widgets restart from the saved value whenever
        # that value changes (for example after another administrator edits the account).
        new_role = st.selectbox("New role", ROLES, index=ROLES.index(target["role"]),
                                key=f"role_{target_id}_{target['role']}")
        active = st.checkbox("Account active", value=target["active"],
                             key=f"active_{target_id}_{target['active']}")
        changed = st.form_submit_button("Save account")
    if changed:
        try:
            auth.change_user(actor, target_id, role=new_role, active=active)
            st.session_state[LAST_TARGET_KEY] = target_id
            st.session_state[FLASH_KEY] = (f"Account updated: {target['username']}. "
                                           "A new role applies at their next login.")
            # The table and selector above were drawn before the save was processed. A
            # rerun redraws them from the stored data; the flash message survives it.
            st.rerun()
        except (ValueError, PermissionError) as error:
            st.error(str(error))

    # --- Access log (UC-10) --------------------------------------------------------
    st.subheader("Access log")
    entries = audit.list_entries(actor)
    if not entries:
        st.info("No entries to show.")
        return
    names = {user["id"]: user["username"] for user in users}  # ids -> usernames; no profile data
    st.dataframe([{"Time": entry["timestamp"],
                   "Acting user": names.get(entry["actor_id"], entry["actor_id"]),
                   "Action": entry["action"],
                   "Target": names.get(entry["target_id"], entry["target_id"])}
                  for entry in entries], hide_index=True)
