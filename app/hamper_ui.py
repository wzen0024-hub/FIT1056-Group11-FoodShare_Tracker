"""Safe hamper generation and anonymised packing screen."""

import streamlit as st


def render(actor, hampers, profiles, inventory):
    st.header("Safe hampers" if actor["role"] == "Staff" else "Packing view")
    if actor["role"] == "Staff":
        clients = profiles.list_clients(actor)
        ready = [c for c in clients if profiles.get_profile(actor, c["id"])]
        if ready:
            client = st.selectbox("Client profile", ready, format_func=lambda c: c["username"])
            if st.button("Generate Safe Packing List"):
                try:
                    hampers.generate(actor, client["id"])
                    st.success("Pending hamper generated")
                    st.rerun()
                except (ValueError, PermissionError) as error:
                    st.error(str(error))
            history = hampers.client_history(actor, client["id"])
            if history:
                with st.expander("Hamper history"):
                    st.dataframe(history, hide_index=True)
        else:
            st.info("Create a consenting client profile before generating a hamper.")

    pending = hampers.pending_for_packing(actor)
    if not pending:
        st.info("No pending hampers")
        return
    for hamper in pending:
        st.subheader(f"Hamper {hamper['id'][:8]}")
        st.dataframe(hamper["items"], hide_index=True)
        if st.button("Mark Packed", key=f"pack-{hamper['id']}"):
            try:
                hampers.mark_packed(actor, hamper["id"])
                st.success("Hamper packed and stock updated")
                st.rerun()
            except (ValueError, PermissionError) as error:
                st.error(str(error))
        with st.expander("Add another item"):
            items = [x for x in inventory.list_items(actor) if x["quantity"] > 0]
            if items:
                candidate = st.selectbox("Inventory item", items, key=f"candidate-{hamper['id']}",
                                         format_func=lambda x: x["name"])
                if st.button("Add item", key=f"add-{hamper['id']}"):
                    try:
                        hampers.add_item(actor, hamper["id"], candidate["id"])
                        st.success("Item added")
                        st.rerun()
                    except (ValueError, PermissionError) as error:
                        st.error(str(error))
