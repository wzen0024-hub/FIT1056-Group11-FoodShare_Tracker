"""Donor offer and staff drop-off setup screens."""

from datetime import date

import streamlit as st


def render(actor, donations):
    if actor["role"] == "Staff":
        st.header("Donor setup")
        with st.form("priority_categories"):
            categories = st.text_input("Priority categories (comma separated)",
                                       value=", ".join(donations.priorities(actor)))
            saved = st.form_submit_button("Save priorities")
        if saved:
            donations.set_priorities(actor, categories.split(","))
            st.success("Priority categories saved")
        with st.form("dropoff_slot"):
            day = st.date_input("Drop-off date", min_value=date.today())
            start = st.time_input("Start time")
            added = st.form_submit_button("Add drop-off slot")
        if added:
            try:
                donations.define_slot(actor, day, start.strftime("%H:%M"))
                st.success("Slot added")
            except ValueError as error:
                st.error(str(error))
        st.dataframe(donations.available_slots(actor), hide_index=True)
        return

    st.header("Donation offers")
    priorities = donations.priorities(actor)
    st.info("Currently needed: " + (", ".join(priorities) if priorities else "No priority categories set"))
    with st.form("new_offer"):
        category = st.text_input("Item category")
        quantity = st.number_input("Estimated quantity", min_value=1, step=1)
        submitted = st.form_submit_button("Submit offer")
    if submitted:
        try:
            donations.submit_offer(actor, {category: int(quantity)})
            st.success("Offer submitted. Book a drop-off below.")
            st.rerun()
        except (ValueError, PermissionError) as error:
            st.error(str(error))

    offers = [offer for offer in donations.own_offers(actor) if not offer["slot_id"]]
    if not offers:
        return
    st.subheader("Book a drop-off")
    available = donations.available_slots(actor)
    if not available:
        st.warning("No available slots. Please choose another date later.")
        return
    with st.form("book_slot"):
        offer = st.selectbox("Offer", offers,
                             format_func=lambda x: ", ".join(x["items"]))
        slot = st.selectbox("Available date and time", available,
                            format_func=lambda x: f"{x['date']} {x['start_time']}")
        checked = st.checkbox("I have checked that my food is safe, correctly stored and within expiry")
        booked = st.form_submit_button("Confirm booking")
    if booked:
        try:
            receipt = donations.book(actor, offer["id"], slot["id"], checked)
            st.success(f"Booking confirmed — {receipt['date']} {receipt['start_time']}. "
                       f"Receipt: {receipt['receipt_id']}")
        except (ValueError, PermissionError) as error:
            st.error(str(error))
