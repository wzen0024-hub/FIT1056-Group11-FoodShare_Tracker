"""Inventory view and staff intake form (filename retained as provided)."""

from datetime import date

import streamlit as st

from app.client_ui import ALLERGENS, SUITABILITY


def render(actor, inventory):
    st.header("Inventory")
    rows = inventory.list_items(actor)
    for item in rows:
        label = (f"{item['name']} | {item['category']} | qty {item['quantity']} | "
                 f"expires {item['expiry_date']}")
        if item["expires_soon"]:
            st.error("Warning: expires within 48 hours — " + label)
        else:
            st.write(label)

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
                inventory.add_item(actor, name=name, category=category,
                                   quantity=int(quantity), expiry_date=expiry,
                                   allergen_tags=allergens or None, dietary_tags=dietary or None)
                st.success("Item added")
                st.rerun()
            except (ValueError, PermissionError) as error:
                st.error(str(error))

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
