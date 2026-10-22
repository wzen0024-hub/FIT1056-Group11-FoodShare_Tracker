"""Donor offer and staff drop-off setup screens."""

from datetime import date

import streamlit as st

from src.domain.donation_offer import offer_from_rows

OFFER_ROWS = 5                      # category lines on the offer form (FR-04.1: at least one)
FLASH_KEY = "donor_flash"           # one-off message shown after a deliberate st.rerun()
GENERATION_KEY = "offer_form_generation"


def _describe_offer(offer):
    """'Rice (3), Fruit (2)' for the offer selector."""
    return ", ".join(f"{category} ({quantity})" for category, quantity in offer["items"].items())


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
    message = st.session_state.pop(FLASH_KEY, None)
    if message:
        st.success(message)
    priorities = donations.priorities(actor)
    st.info("Currently needed: " + (", ".join(priorities) if priorities else "No priority categories set"))

    # --- New offer: one or more categories, each with a quantity (FR-04.1) ----------
    # The widget keys contain a generation number. A successful submit increases it, which
    # gives the form fresh empty widgets (so the same offer cannot be sent twice), while a
    # failed submit keeps everything the donor typed.
    generation = st.session_state.setdefault(GENERATION_KEY, 0)
    st.caption(f"List up to {OFFER_ROWS} item categories with an estimated quantity for each. "
               "Leave unused lines empty.")
    with st.form("new_offer"):
        rows = []
        for number in range(1, OFFER_ROWS + 1):
            # Line 1 keeps the original labels ("Item category" / "Estimated quantity") so the
            # existing UI test and the donor's familiar form still match; extra lines are numbered.
            suffix = "" if number == 1 else f" {number}"
            name_column, quantity_column = st.columns([3, 1])
            category = name_column.text_input(f"Item category{suffix}",
                                              key=f"offer_category_{generation}_{number}")
            # Line 1 starts at 1 as before; spare lines start at 0, which offer_from_rows treats as unused.
            quantity = quantity_column.number_input(f"Estimated quantity{suffix}", min_value=0, step=1,
                                                    value=1 if number == 1 else 0,
                                                    key=f"offer_quantity_{generation}_{number}")
            rows.append((category, int(quantity)))
        submitted = st.form_submit_button("Submit offer")
    if submitted:
        try:
            donations.submit_offer(actor, offer_from_rows(rows))  # rejects empty, blank, zero and repeated lines
            st.session_state[GENERATION_KEY] = generation + 1
            st.session_state[FLASH_KEY] = "Offer submitted. Book a drop-off below."
            st.rerun()
        except (ValueError, PermissionError) as error:
            st.error(str(error))

    offers = [offer for offer in donations.own_offers(actor) if not offer["slot_id"]]
    if not offers:
        return

    # --- Book a drop-off on a chosen date (FR-04.4, FR-04.5) -----------------------
    st.subheader("Book a drop-off")
    dates = donations.available_dates(actor)
    if not dates:
        st.warning("There are currently no bookable drop-off slots, so a booking is not possible yet. "
                   "Please check again later.")
        return
    st.caption("Dates with free slots: " + ", ".join(dates))
    # The date picker is outside the form so the slot list below updates as soon as the
    # donor picks another date. It starts on the earliest date that has a free slot.
    chosen_day = st.date_input("Drop-off date", value=date.fromisoformat(dates[0]), min_value=date.today())
    slots = donations.available_slots(actor, chosen_day)  # only unbooked, future slots on that date
    if not slots:
        st.warning(f"No drop-off slots are available on {chosen_day.isoformat()}. "
                   "Please select an alternative date.")
        return
    with st.form("book_slot"):
        offer = st.selectbox("Offer", offers, format_func=_describe_offer)
        slot = st.selectbox("Available time", slots, format_func=lambda x: f"{x['date']} {x['start_time']}")
        checked = st.checkbox("I have checked that my food is safe, correctly stored and within expiry")
        booked = st.form_submit_button("Confirm booking")
    if booked:
        try:
            receipt = donations.book(actor, offer["id"], slot["id"], checked)
            st.session_state[FLASH_KEY] = (f"Booking confirmed — {receipt['date']} {receipt['start_time']}. "
                                           f"Receipt: {receipt['receipt_id']}")
            st.rerun()  # redraw without the booked slot and offer; the receipt shows in the flash message
        except (ValueError, PermissionError) as error:
            st.error(str(error))
