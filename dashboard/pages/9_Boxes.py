"""
Box Inventory Page

View and manage box stock by type.
"""

import streamlit as st
import sys
import os

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.box_manager import BoxManager

st.set_page_config(page_title="Boxes", page_icon="📦", layout="wide")

# Load boxes from Google Sheets if available
try:
    from core.sheets_storage import is_sheets_enabled, read_boxes
    _sheets_enabled = is_sheets_enabled()
    _sheets_boxes = read_boxes() if _sheets_enabled else []
except Exception:
    _sheets_enabled = False
    _sheets_boxes = []

# Initialize manager
@st.cache_resource
def get_manager():
    return BoxManager()

manager = get_manager()


def main():
    st.title("📦 Box Inventory")

    # Refresh button
    if st.sidebar.button("🔄 Refresh"):
        st.cache_resource.clear()
        st.rerun()

    # Show supplier info in sidebar
    st.sidebar.markdown("### Supplier")
    st.sidebar.markdown(f"**{manager.get_supplier()}**")

    # Show pack sizes
    st.sidebar.markdown("### Pack Sizes")
    for key, config in manager.get_box_types().items():
        st.sidebar.markdown(f"**{config['name']}:** {config['pack_size']} per pack")

    # Tabs
    tab1, tab2, tab3 = st.tabs(["📊 Current Stock", "➕ Add Stock", "➖ Remove Stock"])

    box_types = manager.get_box_types()

    # -------------------------
    # TAB 1: Current Stock
    # -------------------------
    with tab1:
        st.subheader("Box Stock Levels")

        # Get stock from Google Sheets if available, otherwise from manager
        if _sheets_enabled and _sheets_boxes:
            # Convert sheets data to stock summary format
            stock = []
            for item in _sheets_boxes:
                box_config = box_types.get(item.get("box_type", ""), {})
                pack_size = box_config.get("pack_size", 1)
                qty = int(item.get("quantity", 0))
                if qty > 0:
                    stock.append({
                        "box_type": item.get("box_type", ""),
                        "quantity": qty,
                        "packs": qty // pack_size,
                        "loose": qty % pack_size
                    })
        else:
            stock = manager.get_stock_summary()

        if stock:
            table_data = []
            for item in stock:
                type_config = box_types.get(item["box_type"], {})

                table_data.append({
                    "Type": type_config.get("name", item["box_type"]),
                    "Packs": item["packs"],
                    "Loose": item["loose"],
                    "Total Qty": f"{item['quantity']:,}"
                })

            st.dataframe(table_data, use_container_width=True, hide_index=True)

            # Totals
            total_qty = sum(s["quantity"] for s in stock)
            st.success(f"**Total:** {total_qty:,} boxes")
        else:
            st.info("No box stock recorded yet. Use 'Add Stock' tab to add inventory.")

            # Show what types are available
            st.markdown("**Available box types:**")
            for key, config in box_types.items():
                st.markdown(f"- {config['name']}: {config.get('description', '')} ({config['pack_size']} per pack)")

    # -------------------------
    # TAB 2: Add Stock
    # -------------------------
    with tab2:
        st.subheader("Add Boxes to Stock")

        with st.form("add_boxes_form"):
            col1, col2 = st.columns(2)

            with col1:
                box_type = st.selectbox(
                    "Box Type *",
                    options=list(box_types.keys()),
                    format_func=lambda x: box_types[x]["name"]
                )

                pack_size = manager.get_pack_size(box_type)

                # Input method
                input_method = st.radio(
                    "Enter quantity as:",
                    ["Packs", "Individual boxes"],
                    horizontal=True
                )

            with col2:
                if input_method == "Packs":
                    packs = st.number_input(
                        "Number of Packs *",
                        min_value=1,
                        max_value=1000,
                        value=1,
                        help=f"Each pack = {pack_size} boxes"
                    )
                    quantity = packs * pack_size
                    st.markdown(f"**Total boxes:** {quantity:,}")
                else:
                    quantity = st.number_input(
                        "Quantity *",
                        min_value=1,
                        max_value=100000,
                        value=50
                    )
                    packs = quantity // pack_size
                    st.markdown(f"**Equivalent packs:** {packs}")

                source = st.selectbox(
                    "Source",
                    options=["received", "adjustment", "return"]
                )

            notes = st.text_area("Notes (optional)")

            submitted = st.form_submit_button("➕ Add to Stock", type="primary")

            if submitted:
                entry = manager.add_stock(
                    box_type=box_type,
                    quantity=quantity,
                    source=source,
                    notes=notes
                )
                st.success(
                    f"✅ Added {quantity:,} {box_types[box_type]['name']} to stock!\n\n"
                    f"**({packs} packs)**"
                )
                st.cache_resource.clear()

    # -------------------------
    # TAB 3: Remove Stock
    # -------------------------
    with tab3:
        st.subheader("Remove Boxes from Stock")

        stock = manager.get_stock_summary()

        if not stock:
            st.info("No box stock to remove from.")
        else:
            with st.form("remove_boxes_form"):
                # Build options from current stock
                options = []
                for item in stock:
                    type_config = box_types.get(item["box_type"], {})
                    label = f"{type_config.get('name', item['box_type'])} - {item['packs']} packs ({item['quantity']:,} available)"
                    options.append((label, item))

                selected_label = st.selectbox(
                    "Select Box Type *",
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
                    max_qty = selected_item["quantity"] if selected_item else 100
                    quantity = st.number_input(
                        "Quantity to Remove *",
                        min_value=1,
                        max_value=max_qty,
                        value=min(1, max_qty),
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
                        box_type=selected_item["box_type"],
                        quantity=quantity,
                        reason=reason,
                        order_id=order_id if order_id else None
                    )

                    if success:
                        st.success(f"✅ Removed {quantity:,} boxes from stock!")
                        st.cache_resource.clear()
                    else:
                        st.error("Insufficient stock!")


if __name__ == "__main__":
    main()
