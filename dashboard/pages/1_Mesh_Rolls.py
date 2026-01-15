"""
Mesh Rolls Management Page

Add, view, and manage mesh roll inventory.
Includes incoming order tracking and stock position visualization.
"""

import streamlit as st
import sys
import os
from datetime import datetime, timedelta
import pandas as pd
from io import BytesIO

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.mesh_manager import MeshManager

st.set_page_config(page_title="Mesh Rolls", page_icon="📦", layout="wide")

# Initialize manager
@st.cache_resource
def get_manager():
    return MeshManager()

manager = get_manager()


def create_status_bar(on_shelf_pct: float, incoming_pct: float) -> str:
    """
    Create a visual status bar showing on-shelf vs incoming stock.

    Args:
        on_shelf_pct: Percentage of target that's on shelf (0-100+)
        incoming_pct: Percentage of target that's incoming (0-100+)

    Returns:
        HTML string for the status bar
    """
    # Cap at 100% for display but show actual values
    display_on_shelf = min(on_shelf_pct, 100)
    display_incoming = min(incoming_pct, 100 - display_on_shelf)
    gap_pct = max(0, 100 - display_on_shelf - display_incoming)

    bar_html = f"""
    <div style="width:100%; height:20px; background:#e0e0e0; border-radius:4px; overflow:hidden; display:flex;">
        <div style="width:{display_on_shelf}%; background:#4CAF50; height:100%;" title="On-shelf: {on_shelf_pct:.0f}%"></div>
        <div style="width:{display_incoming}%; background:#2196F3; height:100%;" title="Incoming: {incoming_pct:.0f}%"></div>
    </div>
    """
    return bar_html


def main():
    st.title("📦 Mesh Rolls Inventory")

    # Refresh button
    if st.sidebar.button("🔄 Refresh"):
        st.cache_resource.clear()
        st.rerun()

    # Tabs for different actions
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Current Stock",
        "📦 Incoming Orders",
        "➕ Add Stock",
        "➖ Remove Stock",
        "📥 Bulk Import"
    ])

    # -------------------------
    # TAB 1: Current Stock
    # -------------------------
    with tab1:
        st.subheader("Current Inventory")

        summary = manager.get_inventory_summary()
        incoming_summary = manager.get_incoming_summary()
        all_colours = sorted(manager.get_colours())
        mesh_types_config = manager.get_mesh_types()

        # Build incoming lookup
        incoming_lookup = {}
        for item in incoming_summary:
            key = (item["mesh_type"], item["width_mm"], item["length_m"], item["colour"])
            incoming_lookup[key] = item

        # Filters
        col1, col2, col3 = st.columns(3)

        with col1:
            filter_type = st.selectbox(
                "Filter by Type",
                ["All"] + list(mesh_types_config.keys()),
                format_func=lambda x: mesh_types_config[x]["name"] if x != "All" else "All",
                key="filter_type"
            )

        with col2:
            # Get all possible widths
            all_widths = set()
            for mt in mesh_types_config.values():
                all_widths.update(mt["widths"])
            filter_width = st.selectbox(
                "Filter by Width",
                ["All"] + sorted(all_widths),
                key="filter_width"
            )

        with col3:
            filter_colour = st.selectbox(
                "Filter by Colour",
                ["All"] + all_colours,
                key="filter_colour"
            )

        # Build lookup for existing stock
        stock_lookup = {}
        for item in summary:
            key = (item["mesh_type"], item["width_mm"], item["length_m"], item["colour"])
            stock_lookup[key] = item

        # Build full table with all colours
        table_data = []
        for mesh_type, config in mesh_types_config.items():
            if filter_type != "All" and mesh_type != filter_type:
                continue

            for width in config["widths"]:
                if filter_width != "All" and width != filter_width:
                    continue

                for length in config["lengths"]:
                    for colour in all_colours:
                        if filter_colour != "All" and colour != filter_colour:
                            continue

                        key = (mesh_type, width, length, colour)

                        # On-shelf stock
                        if key in stock_lookup:
                            item = stock_lookup[key]
                            quantity = item["quantity"]
                            total_metres = item["total_metres"]
                        else:
                            quantity = 0
                            total_metres = 0

                        # Incoming stock
                        if key in incoming_lookup:
                            incoming_qty = incoming_lookup[key]["quantity"]
                            incoming_metres = incoming_lookup[key]["total_metres"]
                        else:
                            incoming_qty = 0
                            incoming_metres = 0

                        # Calculate target (6 months stock based on usage)
                        daily_usage = manager.get_average_daily_usage(mesh_type, width, colour)
                        target_metres = daily_usage * 180  # 6 months

                        # Calculate percentages for status bar
                        if target_metres > 0:
                            on_shelf_pct = (total_metres / target_metres) * 100
                            incoming_pct = (incoming_metres / target_metres) * 100
                            status_text = f"{on_shelf_pct:.0f}% shelf + {incoming_pct:.0f}% incoming"
                        else:
                            on_shelf_pct = 0
                            incoming_pct = 0
                            status_text = "No usage data"

                        table_data.append({
                            "Mesh Type": config.get("name", mesh_type),
                            "Width": f"{width}mm",
                            "Length": f"{length}m",
                            "Colour": colour,
                            "On Shelf": quantity,
                            "Incoming": incoming_qty,
                            "Total": quantity + incoming_qty,
                            "Metres": f"{total_metres}m",
                            "Status": status_text,
                            "_on_shelf_pct": on_shelf_pct,
                            "_incoming_pct": incoming_pct
                        })

        # Display table
        if table_data:
            # Legend
            st.markdown("""
            <div style="display:flex; gap:20px; margin-bottom:10px; font-size:12px;">
                <span><span style="background:#4CAF50; padding:2px 8px; border-radius:3px; color:white;">Green</span> = On-shelf</span>
                <span><span style="background:#2196F3; padding:2px 8px; border-radius:3px; color:white;">Blue</span> = Incoming</span>
                <span><span style="background:#e0e0e0; padding:2px 8px; border-radius:3px;">Gray</span> = Gap to 6-month target</span>
            </div>
            """, unsafe_allow_html=True)

            # Display with status bars
            for row in table_data:
                col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2, 1, 1, 1.5, 1, 1, 1, 3])

                with col1:
                    st.write(row["Mesh Type"])
                with col2:
                    st.write(row["Width"])
                with col3:
                    st.write(row["Length"])
                with col4:
                    st.write(row["Colour"])
                with col5:
                    st.write(str(row["On Shelf"]))
                with col6:
                    if row["Incoming"] > 0:
                        st.write(f"📦 {row['Incoming']}")
                    else:
                        st.write("-")
                with col7:
                    st.write(row["Metres"])
                with col8:
                    if row["_on_shelf_pct"] > 0 or row["_incoming_pct"] > 0:
                        st.markdown(
                            create_status_bar(row["_on_shelf_pct"], row["_incoming_pct"]),
                            unsafe_allow_html=True
                        )
                    else:
                        st.caption("No usage data")

            # Totals
            total_on_shelf = sum(d["On Shelf"] for d in table_data)
            total_incoming = sum(d["Incoming"] for d in table_data)
            total_metres = sum(int(d["Metres"].replace("m", "")) for d in table_data)

            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("On Shelf", f"{total_on_shelf} rolls")
            with col2:
                st.metric("Incoming", f"{total_incoming} rolls")
            with col3:
                st.metric("Total Metres", f"{total_metres}m")
        else:
            st.info("No items match your filters.")

    # -------------------------
    # TAB 2: Incoming Orders
    # -------------------------
    with tab2:
        st.subheader("📦 Incoming Orders (Stock on the Way)")
        st.info("Track mesh orders that have been placed but not yet received. 4-month lead time for mesh orders.")

        # Add new incoming order
        with st.expander("➕ Add Incoming Order", expanded=False):
            with st.form("add_incoming_form"):
                col1, col2 = st.columns(2)

                with col1:
                    mesh_types = manager.get_mesh_types()
                    inc_mesh_type = st.selectbox(
                        "Mesh Type *",
                        options=list(mesh_types.keys()),
                        format_func=lambda x: mesh_types[x]["name"],
                        key="inc_mesh_type"
                    )

                    valid_widths = mesh_types[inc_mesh_type]["widths"]
                    inc_width = st.selectbox(
                        "Width (mm) *",
                        options=valid_widths,
                        key="inc_width"
                    )

                    valid_lengths = mesh_types[inc_mesh_type]["lengths"]
                    inc_length = st.selectbox(
                        "Length (m) *",
                        options=valid_lengths,
                        key="inc_length"
                    )

                with col2:
                    inc_colour = st.selectbox(
                        "Colour *",
                        options=sorted(manager.get_colours()),
                        key="inc_colour"
                    )

                    inc_quantity = st.number_input(
                        "Quantity (rolls) *",
                        min_value=1,
                        max_value=1000,
                        value=10,
                        key="inc_quantity"
                    )

                col3, col4 = st.columns(2)
                with col3:
                    inc_order_date = st.date_input(
                        "Order Date *",
                        value=datetime.now(),
                        key="inc_order_date"
                    )

                with col4:
                    # Default to 4 months from now
                    default_delivery = datetime.now() + timedelta(days=120)
                    inc_expected_delivery = st.date_input(
                        "Expected Delivery *",
                        value=default_delivery,
                        key="inc_expected_delivery"
                    )

                submitted = st.form_submit_button("➕ Add Incoming Order", type="primary")

                if submitted:
                    try:
                        entry = manager.add_incoming_order(
                            mesh_type=inc_mesh_type,
                            width_mm=inc_width,
                            length_m=inc_length,
                            colour=inc_colour,
                            quantity=inc_quantity,
                            order_date=inc_order_date.strftime("%Y-%m-%d"),
                            expected_delivery=inc_expected_delivery.strftime("%Y-%m-%d")
                        )
                        st.success(
                            f"✅ Added incoming order: {inc_quantity} x {mesh_types[inc_mesh_type]['name']} "
                            f"{inc_width}mm x {inc_length}m ({inc_colour})"
                        )
                        st.cache_resource.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error adding incoming order: {e}")

        # CSV Upload for incoming orders
        with st.expander("📥 Bulk Import Incoming Orders", expanded=False):
            st.info("Upload a CSV or Excel file to import multiple incoming orders at once.")

            # Download template button
            template_csv = """mesh_type,width_mm,length_m,colour,quantity,order_date,expected_delivery
4mm_aluminium,250,10,Monument,10,2026-01-12,2026-05-12
4mm_aluminium,250,10,Woodland Grey,10,2026-01-12,2026-05-12
4mm_aluminium,500,10,Basalt,5,2026-01-12,2026-05-12"""

            st.download_button(
                label="📄 Download CSV Template",
                data=template_csv,
                file_name="incoming_orders_template.csv",
                mime="text/csv",
                help="Download a sample CSV template to fill in"
            )

            # Expected format
            with st.expander("📋 Expected File Format"):
                st.markdown("""
                Your file should have these columns:

                | Column | Required | Description | Example |
                |--------|----------|-------------|---------|
                | mesh_type | Yes | `4mm_aluminium` or `2mm_ember_guard` | 4mm_aluminium |
                | width_mm | Yes | Width in mm (250, 500, 750, 1000) | 250 |
                | length_m | Yes | Length in metres (10, 20, 30) | 10 |
                | colour | Yes | Colorbond colour name | Monument |
                | quantity | Yes | Number of rolls | 10 |
                | order_date | No | Date ordered (YYYY-MM-DD) | 2026-01-12 |
                | expected_delivery | No | Expected delivery (YYYY-MM-DD) | 2026-05-12 |
                """)

            # Two options: file uploader or file path
            st.markdown("**Option 1: Upload file**")
            incoming_file = st.file_uploader(
                "Upload Excel or CSV file",
                type=["xlsx", "xls", "csv"],
                help="Supported formats: .xlsx, .xls, .csv",
                key="incoming_file_uploader"
            )

            st.markdown("**Option 2: Enter file path**")
            file_path_input = st.text_input(
                "File path",
                placeholder="/path/to/your/file.csv",
                help="Paste the full path to your CSV or Excel file"
            )

            if file_path_input:
                load_from_path = st.button("📂 Load from Path", key="load_path_btn")
                if load_from_path:
                    try:
                        if file_path_input.endswith('.csv'):
                            df_incoming = pd.read_csv(file_path_input)
                        else:
                            df_incoming = pd.read_excel(file_path_input)
                        st.session_state['incoming_df'] = df_incoming
                        st.success(f"✅ Loaded {len(df_incoming)} rows from file")
                    except FileNotFoundError:
                        st.error(f"File not found: {file_path_input}")
                    except Exception as e:
                        st.error(f"Error reading file: {e}")

            # Get dataframe from either source
            df_incoming = None
            if 'incoming_df' in st.session_state:
                df_incoming = st.session_state['incoming_df']
            elif incoming_file is not None:
                try:
                    # Read file based on type
                    if incoming_file.name.endswith('.csv'):
                        df_incoming = pd.read_csv(incoming_file)
                    else:
                        df_incoming = pd.read_excel(incoming_file)
                    st.session_state['incoming_df'] = df_incoming
                except Exception as e:
                    st.error(f"Error reading file: {e}")

            if df_incoming is not None:
                if df_incoming.empty:
                    st.warning("The uploaded file is empty.")
                else:
                    st.success(f"✅ File loaded: {len(df_incoming)} rows found")

                    # Validate data
                    mesh_types = manager.get_mesh_types()

                    validated_incoming = []
                    for idx, row in df_incoming.iterrows():
                        errors = []

                        # Check mesh_type
                        mesh_type = str(row.get('mesh_type', '')).strip()
                        if mesh_type not in mesh_types:
                            errors.append(f"Invalid mesh_type: '{mesh_type}'")

                        # Check width
                        try:
                            width = int(row.get('width_mm', 0))
                            if mesh_type in mesh_types and width not in mesh_types[mesh_type]['widths']:
                                errors.append(f"Invalid width {width}mm for {mesh_type}")
                        except (ValueError, TypeError):
                            errors.append(f"Invalid width: '{row.get('width_mm')}'")
                            width = 0

                        # Check length
                        try:
                            length = int(row.get('length_m', 0))
                            if mesh_type in mesh_types and length not in mesh_types[mesh_type]['lengths']:
                                errors.append(f"Invalid length {length}m for {mesh_type}")
                        except (ValueError, TypeError):
                            errors.append(f"Invalid length: '{row.get('length_m')}'")
                            length = 0

                        # Check colour (case-insensitive)
                        colour_raw = str(row.get('colour', '')).strip()
                        colour_matched = None
                        for c in manager.get_colours():
                            if c.lower() == colour_raw.lower():
                                colour_matched = c
                                break
                        if not colour_matched:
                            errors.append(f"Invalid colour: '{colour_raw}'")

                        # Check quantity
                        try:
                            quantity = int(row.get('quantity', 0))
                            if quantity < 1:
                                errors.append("Quantity must be at least 1")
                        except (ValueError, TypeError):
                            errors.append(f"Invalid quantity: '{row.get('quantity')}'")
                            quantity = 0

                        # Order date (default to today)
                        order_date_raw = str(row.get('order_date', '')).strip()
                        if order_date_raw and order_date_raw.lower() not in ['nan', 'nat', '']:
                            try:
                                pd.to_datetime(order_date_raw)
                                order_date = order_date_raw
                            except:
                                order_date = datetime.now().strftime("%Y-%m-%d")
                        else:
                            order_date = datetime.now().strftime("%Y-%m-%d")

                        # Expected delivery (default to +4 months)
                        expected_raw = str(row.get('expected_delivery', '')).strip()
                        if expected_raw and expected_raw.lower() not in ['nan', 'nat', '']:
                            try:
                                pd.to_datetime(expected_raw)
                                expected_delivery = expected_raw
                            except:
                                expected_delivery = (datetime.now() + timedelta(days=120)).strftime("%Y-%m-%d")
                        else:
                            expected_delivery = (datetime.now() + timedelta(days=120)).strftime("%Y-%m-%d")

                        validated_incoming.append({
                            'row_num': idx + 1,
                            'mesh_type': mesh_type,
                            'width_mm': width,
                            'length_m': length,
                            'colour': colour_matched or colour_raw,
                            'quantity': quantity,
                            'order_date': order_date,
                            'expected_delivery': expected_delivery,
                            'errors': errors,
                            'valid': len(errors) == 0
                        })

                    # Count valid/invalid
                    valid_count = sum(1 for r in validated_incoming if r['valid'])
                    invalid_count = len(validated_incoming) - valid_count

                    # Summary
                    st.markdown("---")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Rows", len(validated_incoming))
                    with col2:
                        st.metric("Valid ✅", valid_count)
                    with col3:
                        st.metric("Invalid ❌", invalid_count)

                    # Side-by-side comparison
                    st.markdown("### Data Verification")

                    left_col, right_col = st.columns(2)

                    with left_col:
                        st.markdown("**📄 Raw Data (from file)**")
                        st.dataframe(df_incoming, use_container_width=True, height=300)

                    with right_col:
                        st.markdown("**✅ Validated Data**")
                        display_data = []
                        for r in validated_incoming:
                            status = "✅" if r['valid'] else "❌"
                            error_text = "; ".join(r['errors']) if r['errors'] else ""
                            display_data.append({
                                "Status": status,
                                "Type": r['mesh_type'],
                                "Width": r['width_mm'],
                                "Length": r['length_m'],
                                "Colour": r['colour'],
                                "Qty": r['quantity'],
                                "Expected": r['expected_delivery'],
                                "Errors": error_text
                            })
                        st.dataframe(display_data, use_container_width=True, height=300)

                    # Show errors detail
                    if invalid_count > 0:
                        with st.expander(f"⚠️ View {invalid_count} Error(s)", expanded=True):
                            for r in validated_incoming:
                                if not r['valid']:
                                    st.error(f"**Row {r['row_num']}:** {'; '.join(r['errors'])}")

                    # Import button
                    st.markdown("---")
                    if valid_count > 0:
                        if st.button(f"📥 Import {valid_count} Incoming Order(s)", type="primary", key="import_incoming_btn"):
                            imported = 0
                            for r in validated_incoming:
                                if r['valid']:
                                    try:
                                        manager.add_incoming_order(
                                            mesh_type=r['mesh_type'],
                                            width_mm=r['width_mm'],
                                            length_m=r['length_m'],
                                            colour=r['colour'],
                                            quantity=r['quantity'],
                                            order_date=r['order_date'],
                                            expected_delivery=r['expected_delivery']
                                        )
                                        imported += 1
                                    except Exception as e:
                                        st.error(f"Error importing row {r['row_num']}: {e}")

                            if imported > 0:
                                st.success(f"🎉 Successfully imported {imported} incoming order(s)!")
                                st.cache_resource.clear()
                                if 'incoming_df' in st.session_state:
                                    del st.session_state['incoming_df']
                                st.balloons()
                    else:
                        st.warning("No valid rows to import. Please fix the errors and re-upload.")

        # Display current incoming orders
        incoming_orders = manager.get_incoming_orders()

        if not incoming_orders:
            st.info("No incoming orders. Add an order above when you place a new mesh order.")
        else:
            st.markdown(f"**{len(incoming_orders)} order(s) on the way**")

            for order in incoming_orders:
                mesh_config = manager.get_mesh_types().get(order["mesh_type"], {})
                mesh_name = mesh_config.get("name", order["mesh_type"])

                # Calculate days until delivery
                expected = datetime.strptime(order["expected_delivery"], "%Y-%m-%d")
                days_until = (expected - datetime.now()).days

                if days_until < 0:
                    status_badge = "🔴 OVERDUE"
                    status_color = "#ff4444"
                elif days_until <= 14:
                    status_badge = "🟡 Due Soon"
                    status_color = "#ffaa00"
                else:
                    status_badge = "🟢 On Track"
                    status_color = "#44aa44"

                with st.container():
                    col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])

                    with col1:
                        st.write(f"**{mesh_name}** {order['width_mm']}mm x {order['length_m']}m")
                        st.caption(f"{order['colour']}")

                    with col2:
                        st.write(f"**{order['quantity']}** rolls")
                        st.caption(f"{order['quantity'] * order['length_m']}m total")

                    with col3:
                        st.write(f"Ordered: {order['order_date']}")

                    with col4:
                        st.write(f"Expected: {order['expected_delivery']}")
                        st.caption(f"{status_badge} ({days_until} days)")

                    with col5:
                        if st.button("✅ Received", key=f"recv_{order['id']}"):
                            manager.mark_order_received(order["id"])
                            st.cache_resource.clear()
                            st.rerun()
                        if st.button("❌ Cancel", key=f"cancel_{order['id']}"):
                            manager.cancel_incoming_order(order["id"])
                            st.cache_resource.clear()
                            st.rerun()

                    st.markdown("---")

    # -------------------------
    # TAB 3: Add Stock
    # -------------------------
    with tab3:
        st.subheader("Add Mesh Rolls to Inventory")

        with st.form("add_stock_form"):
            col1, col2 = st.columns(2)

            with col1:
                mesh_types = manager.get_mesh_types()
                mesh_type = st.selectbox(
                    "Mesh Type *",
                    options=list(mesh_types.keys()),
                    format_func=lambda x: mesh_types[x]["name"]
                )

                # Get valid widths for selected type
                valid_widths = mesh_types[mesh_type]["widths"]
                width = st.selectbox(
                    "Width (mm) *",
                    options=valid_widths
                )

                # Get valid lengths for selected type
                valid_lengths = mesh_types[mesh_type]["lengths"]
                length = st.selectbox(
                    "Length (m) *",
                    options=valid_lengths
                )

            with col2:
                colour = st.selectbox(
                    "Colour *",
                    options=sorted(manager.get_colours())
                )

                quantity = st.number_input(
                    "Quantity (rolls) *",
                    min_value=1,
                    max_value=1000,
                    value=1
                )

                received_date = st.date_input(
                    "Received Date",
                    value=datetime.now()
                )

            location = st.text_input("Location", value="Warehouse")
            notes = st.text_area("Notes (optional)")

            submitted = st.form_submit_button("➕ Add to Inventory", type="primary")

            if submitted:
                try:
                    entry = manager.add_roll(
                        mesh_type=mesh_type,
                        width_mm=width,
                        length_m=length,
                        colour=colour,
                        quantity=quantity,
                        received_date=received_date.strftime("%Y-%m-%d"),
                        location=location,
                        notes=notes
                    )
                    st.success(
                        f"✅ Added {quantity} x {mesh_types[mesh_type]['name']} "
                        f"{width}mm x {length}m ({colour}) to inventory!"
                    )
                    st.cache_resource.clear()
                except Exception as e:
                    st.error(f"Error adding stock: {e}")

    # -------------------------
    # TAB 4: Remove Stock
    # -------------------------
    with tab4:
        st.subheader("Remove Mesh Rolls from Inventory")

        summary = manager.get_inventory_summary()

        if not summary:
            st.info("No inventory to remove from.")
        else:
            with st.form("remove_stock_form"):
                # Build options from current inventory
                options = []
                for item in summary:
                    mesh_config = manager.get_mesh_types().get(item["mesh_type"], {})
                    label = (
                        f"{mesh_config.get('name', item['mesh_type'])} - "
                        f"{item['width_mm']}mm x {item['length_m']}m - "
                        f"{item['colour']} ({item['quantity']} available)"
                    )
                    options.append((label, item))

                selected_label = st.selectbox(
                    "Select Product *",
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
                        value=1
                    )

                with col2:
                    reason = st.selectbox(
                        "Reason *",
                        options=["order", "damaged", "adjustment", "other"]
                    )

                order_id = st.text_input("Order ID (optional)")

                submitted = st.form_submit_button("➖ Remove from Inventory", type="primary")

                if submitted and selected_item:
                    success = manager.remove_roll(
                        mesh_type=selected_item["mesh_type"],
                        width_mm=selected_item["width_mm"],
                        length_m=selected_item["length_m"],
                        colour=selected_item["colour"],
                        quantity=quantity,
                        reason=reason,
                        order_id=order_id if order_id else None
                    )

                    if success:
                        st.success(f"✅ Removed {quantity} roll(s) from inventory!")
                        st.cache_resource.clear()
                    else:
                        st.error("Insufficient stock!")

    # -------------------------
    # TAB 5: Bulk Import
    # -------------------------
    with tab5:
        st.subheader("Bulk Import Mesh Rolls")
        st.info(
            "Upload an Excel (.xlsx) or CSV file to import multiple mesh rolls at once. "
            "Review the data before confirming the import."
        )

        # Expected format
        with st.expander("📋 Expected File Format"):
            st.markdown("""
            Your file should have these columns:

            | Column | Required | Description | Example |
            |--------|----------|-------------|---------|
            | mesh_type | Yes | `4mm_aluminium` or `2mm_ember_guard` | 4mm_aluminium |
            | width_mm | Yes | Width in mm (250, 500, 750, 1000) | 250 |
            | length_m | Yes | Length in metres (10, 20, 30) | 10 |
            | colour | Yes | Colorbond colour name | Monument |
            | quantity | Yes | Number of rolls | 5 |
            | received_date | No | Date received (YYYY-MM-DD) | 2026-01-11 |
            | location | No | Storage location | Warehouse |
            | notes | No | Any notes | |
            """)

        # File uploader
        uploaded_file = st.file_uploader(
            "Upload Excel or CSV file",
            type=["xlsx", "xls", "csv"],
            help="Supported formats: .xlsx, .xls, .csv"
        )

        if uploaded_file is not None:
            try:
                # Read file based on type
                if uploaded_file.name.endswith('.csv'):
                    df_raw = pd.read_csv(uploaded_file)
                else:
                    df_raw = pd.read_excel(uploaded_file)

                if df_raw.empty:
                    st.warning("The uploaded file is empty.")
                else:
                    st.success(f"✅ File loaded: {len(df_raw)} rows found")

                    # Validate data
                    mesh_types = manager.get_mesh_types()
                    valid_colours = [c.lower() for c in manager.get_colours()]

                    validated_rows = []
                    for idx, row in df_raw.iterrows():
                        errors = []

                        # Check mesh_type
                        mesh_type = str(row.get('mesh_type', '')).strip()
                        if mesh_type not in mesh_types:
                            errors.append(f"Invalid mesh_type: '{mesh_type}'")

                        # Check width
                        try:
                            width = int(row.get('width_mm', 0))
                            if mesh_type in mesh_types and width not in mesh_types[mesh_type]['widths']:
                                errors.append(f"Invalid width {width}mm for {mesh_type}")
                        except (ValueError, TypeError):
                            errors.append(f"Invalid width: '{row.get('width_mm')}'")
                            width = 0

                        # Check length
                        try:
                            length = int(row.get('length_m', 0))
                            if mesh_type in mesh_types and length not in mesh_types[mesh_type]['lengths']:
                                errors.append(f"Invalid length {length}m for {mesh_type}")
                        except (ValueError, TypeError):
                            errors.append(f"Invalid length: '{row.get('length_m')}'")
                            length = 0

                        # Check colour (case-insensitive)
                        colour_raw = str(row.get('colour', '')).strip()
                        colour_matched = None
                        for c in manager.get_colours():
                            if c.lower() == colour_raw.lower():
                                colour_matched = c
                                break
                        if not colour_matched:
                            errors.append(f"Invalid colour: '{colour_raw}'")

                        # Check quantity
                        try:
                            quantity = int(row.get('quantity', 0))
                            if quantity < 1:
                                errors.append("Quantity must be at least 1")
                        except (ValueError, TypeError):
                            errors.append(f"Invalid quantity: '{row.get('quantity')}'")
                            quantity = 0

                        # Optional fields
                        received_date = str(row.get('received_date', '')).strip()
                        if received_date and received_date.lower() not in ['nan', 'nat', '']:
                            try:
                                pd.to_datetime(received_date)
                            except:
                                received_date = datetime.now().strftime("%Y-%m-%d")
                        else:
                            received_date = datetime.now().strftime("%Y-%m-%d")

                        location = str(row.get('location', 'Warehouse')).strip()
                        if location.lower() in ['nan', '']:
                            location = 'Warehouse'

                        notes = str(row.get('notes', '')).strip()
                        if notes.lower() == 'nan':
                            notes = ''

                        validated_rows.append({
                            'row_num': idx + 1,
                            'mesh_type': mesh_type,
                            'width_mm': width,
                            'length_m': length,
                            'colour': colour_matched or colour_raw,
                            'quantity': quantity,
                            'received_date': received_date,
                            'location': location,
                            'notes': notes,
                            'errors': errors,
                            'valid': len(errors) == 0
                        })

                    # Count valid/invalid
                    valid_count = sum(1 for r in validated_rows if r['valid'])
                    invalid_count = len(validated_rows) - valid_count

                    # Summary
                    st.markdown("---")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Rows", len(validated_rows))
                    with col2:
                        st.metric("Valid ✅", valid_count)
                    with col3:
                        st.metric("Invalid ❌", invalid_count)

                    # Side-by-side comparison
                    st.markdown("### Data Verification")

                    left_col, right_col = st.columns(2)

                    with left_col:
                        st.markdown("**📄 Raw Data (from file)**")
                        st.dataframe(df_raw, use_container_width=True, height=300)

                    with right_col:
                        st.markdown("**✅ Validated Data**")
                        # Build display data
                        display_data = []
                        for r in validated_rows:
                            status = "✅" if r['valid'] else "❌"
                            error_text = "; ".join(r['errors']) if r['errors'] else ""
                            display_data.append({
                                "Status": status,
                                "Type": r['mesh_type'],
                                "Width": r['width_mm'],
                                "Length": r['length_m'],
                                "Colour": r['colour'],
                                "Qty": r['quantity'],
                                "Errors": error_text
                            })
                        st.dataframe(display_data, use_container_width=True, height=300)

                    # Show errors detail
                    if invalid_count > 0:
                        with st.expander(f"⚠️ View {invalid_count} Error(s)", expanded=True):
                            for r in validated_rows:
                                if not r['valid']:
                                    st.error(f"**Row {r['row_num']}:** {'; '.join(r['errors'])}")

                    # Import button
                    st.markdown("---")
                    if valid_count > 0:
                        if st.button(f"📥 Import {valid_count} Valid Row(s)", type="primary"):
                            imported = 0
                            for r in validated_rows:
                                if r['valid']:
                                    try:
                                        manager.add_roll(
                                            mesh_type=r['mesh_type'],
                                            width_mm=r['width_mm'],
                                            length_m=r['length_m'],
                                            colour=r['colour'],
                                            quantity=r['quantity'],
                                            received_date=r['received_date'],
                                            location=r['location'],
                                            notes=r['notes']
                                        )
                                        imported += 1
                                    except Exception as e:
                                        st.error(f"Error importing row {r['row_num']}: {e}")

                            if imported > 0:
                                st.success(f"🎉 Successfully imported {imported} roll(s) to inventory!")
                                st.cache_resource.clear()
                                st.balloons()
                    else:
                        st.warning("No valid rows to import. Please fix the errors and re-upload.")

            except Exception as e:
                st.error(f"Error reading file: {e}")


if __name__ == "__main__":
    main()
