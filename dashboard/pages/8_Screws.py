"""
Screw Inventory Page

View and manage screw stock by type and colour.
"""

import streamlit as st
import sys
import os

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.screw_manager import ScrewManager

st.set_page_config(page_title="Screws", page_icon="🔩", layout="wide")

# Initialize manager
@st.cache_resource
def get_manager():
    return ScrewManager()

manager = get_manager()


def main():
    st.title("🔩 Screw Inventory")

    # Refresh button
    if st.sidebar.button("🔄 Refresh"):
        st.cache_resource.clear()
        st.rerun()

    # Show supplier info in sidebar
    st.sidebar.markdown("### Supplier")
    st.sidebar.markdown(f"**{manager.get_supplier()}**")
    st.sidebar.markdown(f"Box size: {manager.get_pack_size():,} screws")

    # Tabs
    tab1, tab2, tab3 = st.tabs(["📊 Current Stock", "➕ Add Stock", "➖ Remove Stock"])

    # -------------------------
    # TAB 1: Current Stock
    # -------------------------
    with tab1:
        st.subheader("Screw Stock Levels")

        stock = manager.get_stock_summary()
        screw_types = manager.get_screw_types()
        pack_size = manager.get_pack_size()
        all_colours = sorted(manager.get_colours())

        # Filters
        col1, col2 = st.columns(2)

        with col1:
            type_options = ["All"] + list(screw_types.keys())
            filter_type = st.selectbox(
                "Filter by Type",
                options=type_options,
                format_func=lambda x: screw_types[x]["name"] if x != "All" else "All Types",
                key="filter_type"
            )

        with col2:
            filter_colour = st.selectbox(
                "Filter by Colour",
                options=["All"] + all_colours,
                key="filter_colour"
            )

        # Build lookup for existing stock
        stock_lookup = {}
        for item in stock:
            key = (item["screw_type"], item["colour"])
            stock_lookup[key] = item

        # Build full table with all colours
        table_data = []
        for screw_type, config in screw_types.items():
            if filter_type != "All" and screw_type != filter_type:
                continue

            for colour in all_colours:
                if filter_colour != "All" and colour != filter_colour:
                    continue

                key = (screw_type, colour)
                if key in stock_lookup:
                    quantity = stock_lookup[key]["quantity"]
                else:
                    quantity = 0

                boxes = quantity // pack_size
                loose = quantity % pack_size

                table_data.append({
                    "Type": config.get("name", screw_type),
                    "Colour": colour,
                    "Boxes": boxes,
                    "Loose": loose,
                    "Total Qty": quantity
                })

        # Display table
        if table_data:
            st.dataframe(table_data, use_container_width=True, hide_index=True)

            # Totals
            total_qty = sum(d["Total Qty"] for d in table_data)
            total_boxes = total_qty // pack_size
            st.success(f"**Total:** {total_boxes} boxes ({total_qty:,} screws)")
        else:
            st.info("No screws match your filters.")

    # -------------------------
    # TAB 2: Add Stock
    # -------------------------
    with tab2:
        st.subheader("Add Screws to Stock")

        with st.form("add_screws_form"):
            col1, col2 = st.columns(2)

            with col1:
                screw_type = st.selectbox(
                    "Screw Type *",
                    options=list(screw_types.keys()),
                    format_func=lambda x: screw_types[x]["name"]
                )

                colour = st.selectbox(
                    "Colour *",
                    options=sorted(manager.get_colours())
                )

                # Input method
                input_method = st.radio(
                    "Enter quantity as:",
                    ["Boxes", "Individual screws"],
                    horizontal=True
                )

            with col2:
                if input_method == "Boxes":
                    boxes = st.number_input(
                        "Number of Boxes *",
                        min_value=1,
                        max_value=1000,
                        value=1,
                        help=f"Each box = {pack_size:,} screws"
                    )
                    quantity = boxes * pack_size
                    st.markdown(f"**Total screws:** {quantity:,}")
                else:
                    quantity = st.number_input(
                        "Quantity *",
                        min_value=1,
                        max_value=1000000,
                        value=1000
                    )
                    boxes = quantity // pack_size
                    st.markdown(f"**Equivalent boxes:** {boxes}")

                source = st.selectbox(
                    "Source",
                    options=["received", "adjustment", "return"]
                )

            notes = st.text_area("Notes (optional)")

            submitted = st.form_submit_button("➕ Add to Stock", type="primary")

            if submitted:
                entry = manager.add_stock(
                    screw_type=screw_type,
                    colour=colour,
                    quantity=quantity,
                    source=source,
                    notes=notes
                )
                st.success(
                    f"✅ Added {quantity:,} {screw_types[screw_type]['name']} ({colour}) to stock!\n\n"
                    f"**({boxes} boxes)**"
                )
                st.cache_resource.clear()

    # -------------------------
    # TAB 3: Remove Stock
    # -------------------------
    with tab3:
        st.subheader("Remove Screws from Stock")

        stock = manager.get_stock_summary()

        if not stock:
            st.info("No screw stock to remove from.")
        else:
            with st.form("remove_screws_form"):
                # Build options from current stock
                options = []
                for item in stock:
                    type_config = screw_types.get(item["screw_type"], {})
                    boxes = item["quantity"] // pack_size
                    label = f"{type_config.get('name', item['screw_type'])} - {item['colour']} - {boxes} boxes ({item['quantity']:,} available)"
                    options.append((label, item))

                selected_label = st.selectbox(
                    "Select Screw Type & Colour *",
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
                    max_qty = selected_item["quantity"] if selected_item else 1000
                    quantity = st.number_input(
                        "Quantity to Remove *",
                        min_value=1,
                        max_value=max_qty,
                        value=min(1000, max_qty),
                        help=f"Max available: {max_qty:,}"
                    )

                with col2:
                    reason = st.selectbox(
                        "Reason *",
                        options=["order", "damaged", "adjustment", "other"]
                    )

                order_id = st.text_input("Order ID (optional)")

                submitted = st.form_submit_button("➖ Remove from Stock", type="primary")

                if submitted and selected_item:
                    success = manager.remove_stock(
                        screw_type=selected_item["screw_type"],
                        colour=selected_item["colour"],
                        quantity=quantity,
                        reason=reason,
                        order_id=order_id if order_id else None
                    )

                    if success:
                        st.success(f"✅ Removed {quantity:,} screws from stock!")
                        st.cache_resource.clear()
                    else:
                        st.error("Insufficient stock!")


if __name__ == "__main__":
    main()
