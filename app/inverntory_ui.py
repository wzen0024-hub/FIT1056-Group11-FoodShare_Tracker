"""Inventory view and staff intake form (filename retained as provided)."""

from datetime import date

import streamlit as st

from app.client_ui import ALLERGENS, SUITABILITY


def _render_items(rows):
    """Draw the inventory list: expiry highlight, tags (FR-02.2, AC-21) and issue flags (FR-02.7)."""
    for item in rows:
        label = (f"{item['name']} | {item['category']} | qty {item['quantity']} | "
                 f"expires {item['expiry_date']} | allergens: {', '.join(item.get('allergen_tags', []))} | "
                 f"dietary: {', '.join(item.get('dietary_tags', []))}")
        if item["expires_soon"]:
            st.error("Warning: expires within 48 hours — " + label)
        else:
            st.write(label)
        for issue in item["issues"]:
            st.warning(f"Issue flagged on {item['name']} — {issue['reason']}: {issue['comment']}")


def render(actor, inventory):
    st.header("Inventory")
    # The list is drawn into this placeholder LAST, after the forms below have been
    # handled, so an item added or flagged in this run shows immediately without a
    # st.rerun() (a rerun would also wipe the success message).
    list_area = st.container()

    if actor["role"] == "Staff":
        st.subheader("Record incoming food")
        with st.form("inventory_add"):
            name = st.text_input("Item name")
            category = st.text_input("Category")
            quantity = st.number_input("Quantity", min_value=0, step=1)
            expiry = st.date_input("Expiry date", min_value=date.today())
            allergens = st.multiselect("Allergen tags (select None if none)", ALLERGENS)
            dietary = st.multiselect("Dietary suitability tags (select None if none)", SUITABILITY)
            submitted = st.form_submit_button("Add item")
        if submitted:
            try:
                # An empty selection becomes None so the service reports "select tags, or None".
                # "None" together with real tags is rejected by the service as well.
                inventory.add_item(actor, name=name, category=category,
                                   quantity=int(quantity), expiry_date=expiry,
                                   allergen_tags=allergens or None, dietary_tags=dietary or None)
                st.success("Item added")
            except (ValueError, PermissionError) as error:
                st.error(str(error))

    rows = inventory.list_items(actor)  # read after the add handler so the new item can be flagged
    if actor["role"] in {"Staff", "Volunteer"} and rows:
        st.subheader("Flag an inventory issue")
        with st.form("inventory_issue"):
            item = st.selectbox("Item", rows, format_func=lambda x: f"{x['name']} ({x['id'][:8]})")
            reason = st.selectbox("Reason", ["Damaged", "Spoiled", "Incorrect count"])
            comment = st.text_input("Comment")
            flagged = st.form_submit_button("Submit issue")
        if flagged:
            try:
                inventory.flag_issue(actor, item["id"], reason, comment)
                st.success("Issue flagged for staff review")
            except (ValueError, PermissionError) as error:
                st.error(str(error))

    with list_area:
        _render_items(inventory.list_items(actor))  # fresh read: includes this run's changes
