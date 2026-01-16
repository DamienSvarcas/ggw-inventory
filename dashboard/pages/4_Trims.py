"""
Trim Stock Management Page

View, add, and remove 1m trim stock by colour.
"""

import streamlit as st
import sys
import os

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.saddle_manager import SaddleManager

st.set_page_config(page_title="Trims", page_icon="📏", layout="wide")

# Initialize manager
@st.cache_resource
def get_manager():
    return SaddleManager()

manager = get_manager()

# Fixed type for this page
SADDLE_TYPE = "trim"
TYPE_NAME = "Trims"

# DEBUG: Test Google Sheets directly
try:
    from core.sheets_storage import is_sheets_enabled, read_trims
    _sheets_enabled = is_sheets_enabled()
    _sheets_trims = read_trims() if _sheets_enabled else []
except Exception as e:
    _sheets_enabled = False
    _sheets_trims = []
    st.sidebar.error(f"Sheets error: {e}")


def main():
    st.title("📏 Trim Stock")
    st.caption("1m trim pieces by colour")

    # DEBUG: Show sheets info
    st.sidebar.markdown("---")
    st.sidebar.write(f"**Sheets enabled:** {_sheets_enabled}")
    st.sidebar.write(f"**Trims in Sheets:** {len(_sheets_trims)}")
    if _sheets_trims:
        st.sidebar.write(_sheets_trims[:3])

    # Refresh button
    if st.sidebar.button("🔄 Refresh"):
        st.cache_resource.clear()
        st.rerun()

    # Tabs
    tab1, tab2, tab3 = st.tabs(["📊 Current Stock", "➕ Add Trims", "➖ Remove Trims"])

    all_colours = sorted(manager.get_colours())

    # -------------------------
    # TAB 1: Current Stock
    # -------------------------
    with tab1:
        st.subheader("Current Trim Stock")

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

            table_data.append({
                "Colour": colour,
                "Quantity": quantity
            })

        # Display table
        if table_data:
            st.dataframe(table_data, use_container_width=True, hide_index=True)

            # Totals
            total_trims = sum(d["Quantity"] for d in table_data)
            st.success(f"**Total:** {total_trims:,} trims")
        else:
            st.info("No items match your filter.")

    # -------------------------
    # TAB 2: Add Trims
    # -------------------------
    with tab2:
        st.subheader("Add Trims to Stock")

        with st.form("add_trims_form"):
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
                    value=100,
                    help="Number of 1m trim pieces"
                )

                source = st.selectbox(
                    "Source",
                    options=["production", "external", "adjustment", "return"],
                    help="Where did these trims come from?"
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
                    st.success(f"✅ Added {quantity:,} trims ({colour}) to stock!")
                    st.cache_resource.clear()
                except Exception as e:
                    st.error(f"Error adding trims: {e}")

    # -------------------------
    # TAB 3: Remove Trims
    # -------------------------
    with tab3:
        st.subheader("Remove Trims from Stock")

        # Get stock filtered by type
        all_stock = manager.get_stock_summary()
        stock = [s for s in all_stock if s.get("saddle_type") == SADDLE_TYPE and s.get("quantity", 0) > 0]

        if not stock:
            st.info("No trim stock to remove from.")
        else:
            with st.form("remove_trims_form"):
                # Build options from current stock
                options = []
                for item in stock:
                    label = f"{item['colour']} ({item['quantity']:,} available)"
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
                        value=min(10, max_qty)
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
                        st.success(f"✅ Removed {quantity:,} trims from stock!")
                        st.cache_resource.clear()
                    else:
                        st.error("Insufficient stock!")


if __name__ == "__main__":
    main()
