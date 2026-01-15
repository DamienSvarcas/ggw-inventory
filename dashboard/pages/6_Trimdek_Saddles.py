"""
Trimdek Saddle Stock Management Page

View, add, and remove trimdek saddle stock by colour.
Externally supplied (not produced in-house).
"""

import streamlit as st
import sys
import os

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.saddle_manager import SaddleManager

st.set_page_config(page_title="Trimdek Saddles", page_icon="🔧", layout="wide")

# Initialize manager
@st.cache_resource
def get_manager():
    return SaddleManager()

manager = get_manager()

# Fixed type for this page
SADDLE_TYPE = "trimdek"
TYPE_NAME = "Trimdek Saddles"
PACK_SIZE = 60


def main():
    st.title("🔧 Trimdek Saddle Stock")
    st.caption("Externally supplied saddles")

    # Refresh button
    if st.sidebar.button("🔄 Refresh"):
        st.cache_resource.clear()
        st.rerun()

    # Tabs
    tab1, tab2, tab3 = st.tabs(["📊 Current Stock", "➕ Add Saddles", "➖ Remove Saddles"])

    all_colours = sorted(manager.get_colours())

    # -------------------------
    # TAB 1: Current Stock
    # -------------------------
    with tab1:
        st.subheader("Current Trimdek Saddle Stock")

        # Get stock filtered by type
        all_stock = manager.get_stock_summary()
        stock = [s for s in all_stock if s.get("saddle_type") == SADDLE_TYPE]

        # Filter
        filter_colour = st.selectbox(
            "Filter by Colour",
            ["All"] + all_colours,
            key="filter_colour"
        )

        # Build lookup for existing stock
        stock_lookup = {}
        for item in stock:
            stock_lookup[item["colour"]] = item

        # Build full table with all colours
        table_data = []
        for colour in all_colours:
            if filter_colour != "All" and colour != filter_colour:
                continue

            if colour in stock_lookup:
                quantity = stock_lookup[colour]["quantity"]
            else:
                quantity = 0

            packs = quantity // PACK_SIZE

            table_data.append({
                "Colour": colour,
                "Quantity": quantity,
                "Packs (~60/pack)": f"~{packs:,}"
            })

        # Display table
        if table_data:
            st.dataframe(table_data, use_container_width=True, hide_index=True)

            # Totals
            total_saddles = sum(d["Quantity"] for d in table_data)
            total_packs = total_saddles // PACK_SIZE
            st.success(f"**Total:** {total_saddles:,} saddles (~{total_packs:,} packs)")
        else:
            st.info("No items match your filter.")

    # -------------------------
    # TAB 2: Add Saddles
    # -------------------------
    with tab2:
        st.subheader("Add Trimdek Saddles to Stock")
        st.info("Trimdek saddles are externally supplied.")

        with st.form("add_saddles_form"):
            col1, col2 = st.columns(2)

            with col1:
                colour = st.selectbox(
                    "Colour *",
                    options=all_colours
                )

            with col2:
                quantity = st.number_input(
                    "Quantity *",
                    min_value=1,
                    max_value=100000,
                    value=60,
                    help="Enter number of individual saddles (1 pack ≈ 60)"
                )

                source = st.selectbox(
                    "Source",
                    options=["external", "adjustment", "return", "other"],
                    help="Where did these saddles come from?"
                )

            notes = st.text_area("Notes (optional)")

            submitted = st.form_submit_button("➕ Add to Stock", type="primary")

            if submitted:
                try:
                    entry = manager.add_saddles(
                        saddle_type=SADDLE_TYPE,
                        colour=colour,
                        quantity=quantity,
                        source=source,
                        notes=notes
                    )
                    packs = quantity // PACK_SIZE
                    st.success(f"✅ Added {quantity:,} trimdek saddles ({colour}) to stock! (~{packs} packs)")
                    st.cache_resource.clear()
                except Exception as e:
                    st.error(f"Error adding saddles: {e}")

    # -------------------------
    # TAB 3: Remove Saddles
    # -------------------------
    with tab3:
        st.subheader("Remove Trimdek Saddles from Stock")

        # Get stock filtered by type
        all_stock = manager.get_stock_summary()
        stock = [s for s in all_stock if s.get("saddle_type") == SADDLE_TYPE and s.get("quantity", 0) > 0]

        if not stock:
            st.info("No trimdek saddle stock to remove from.")
        else:
            with st.form("remove_saddles_form"):
                # Build options from current stock
                options = []
                for item in stock:
                    packs = item['quantity'] // PACK_SIZE
                    label = f"{item['colour']} - {packs} packs ({item['quantity']:,} available)"
                    options.append((label, item))

                selected_label = st.selectbox(
                    "Select Colour *",
                    options=[o[0] for o in options]
                )

                # Find selected item
                selected_item = None
                for label, item in options:
                    if label == selected_label:
                        selected_item = item
                        break

                col1, col2 = st.columns(2)

                with col1:
                    max_qty = selected_item["quantity"] if selected_item else 1
                    quantity = st.number_input(
                        "Quantity to Remove *",
                        min_value=1,
                        max_value=max_qty,
                        value=min(66, max_qty)
                    )

                with col2:
                    reason = st.selectbox(
                        "Reason *",
                        options=["order", "damaged", "adjustment", "other"]
                    )

                order_id = st.text_input("Order ID (optional)")

                submitted = st.form_submit_button("➖ Remove from Stock", type="primary")

                if submitted and selected_item:
                    success = manager.remove_saddles(
                        saddle_type=SADDLE_TYPE,
                        colour=selected_item["colour"],
                        quantity=quantity,
                        reason=reason,
                        order_id=order_id if order_id else None
                    )

                    if success:
                        st.success(f"✅ Removed {quantity:,} trimdek saddles from stock!")
                        st.cache_resource.clear()
                    else:
                        st.error("Insufficient stock!")


if __name__ == "__main__":
    main()
