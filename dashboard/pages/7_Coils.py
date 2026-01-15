"""
Coil Inventory & Production Page

Track raw steel coils and log production runs.
"""

import streamlit as st
import sys
import os
from datetime import datetime

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.saddle_manager import SaddleManager

st.set_page_config(page_title="Coils & Production", page_icon="�icing", layout="wide")

# Initialize manager
@st.cache_resource
def get_manager():
    return SaddleManager()

manager = get_manager()


def main():
    st.title("🏭 Coils & Production")

    # Refresh button
    if st.sidebar.button("🔄 Refresh"):
        st.cache_resource.clear()
        st.rerun()

    # Show production config in sidebar
    st.sidebar.markdown("### Production Settings")
    saddle_types = manager.get_saddle_types()
    for type_key, type_config in saddle_types.items():
        if type_config.get("in_house", False):
            yield_val = type_config.get("yield_per_kg", "N/A")
            waste_val = type_config.get("waste_percent", "N/A")
            output_unit = type_config.get("output_unit", "units")
            st.sidebar.markdown(f"**{type_config['name']}:** {yield_val} {output_unit}/kg, {waste_val}% waste")

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📦 Coil Inventory",
        "➕ Add Coil",
        "⚙️ Production Run",
        "📜 Production History"
    ])

    # -------------------------
    # TAB 1: Coil Inventory
    # -------------------------
    with tab1:
        st.subheader("Steel Coil Inventory")

        coils = manager.get_coil_inventory()

        if coils:
            # Filters
            col1, col2 = st.columns(2)

            with col1:
                saddle_types = list(set(c["saddle_type"] for c in coils))
                filter_type = st.selectbox(
                    "Filter by Type",
                    ["All"] + saddle_types,
                    key="coil_filter_type"
                )

            with col2:
                colours = list(set(c["colour"] for c in coils))
                filter_colour = st.selectbox(
                    "Filter by Colour",
                    ["All"] + sorted(colours),
                    key="coil_filter_colour"
                )

            # Apply filters
            filtered = coils
            if filter_type != "All":
                filtered = [c for c in filtered if c["saddle_type"] == filter_type]
            if filter_colour != "All":
                filtered = [c for c in filtered if c["colour"] == filter_colour]

            # Display table
            if filtered:
                # Display names for coil types
                coil_display_names = {
                    "corrugated": "105mm (Corro saddles)",
                    "trim": "25mm (Trims)"
                }

                table_data = []
                for coil in filtered:
                    used_kg = coil["initial_weight_kg"] - coil["current_weight_kg"]
                    percent_used = (used_kg / coil["initial_weight_kg"] * 100) if coil["initial_weight_kg"] > 0 else 0

                    # Calculate remaining yield with type-specific params
                    estimate = manager.calculate_production_estimate(coil["current_weight_kg"], coil["saddle_type"])
                    qty = estimate['expected_saddles']

                    # Format output based on type - trims have no packs
                    if coil["saddle_type"] == "trim":
                        output_display = f"{qty:,} trims"
                    else:
                        packs = qty // 66  # 66 per pack for saddles
                        output_display = f"{packs} packs ({qty:,})"

                    table_data.append({
                        "Type": coil_display_names.get(coil["saddle_type"], coil["saddle_type"]),
                        "Colour": coil["colour"],
                        "Initial (kg)": f"{coil['initial_weight_kg']:.1f}",
                        "Remaining (kg)": f"{coil['current_weight_kg']:.1f}",
                        "Used %": f"{percent_used:.0f}%",
                        "Est. Output Left": output_display
                    })

                st.dataframe(table_data, use_container_width=True, hide_index=True)

                # Summary - show totals by type
                total_kg = sum(c["current_weight_kg"] for c in filtered)
                st.success(f"**Total:** {total_kg:.1f}kg remaining")
            else:
                st.info("No coils match your filters.")
        else:
            st.info("No coils in inventory. Use 'Add Coil' tab to add steel coils.")

    # -------------------------
    # TAB 2: Add Coil
    # -------------------------
    with tab2:
        st.subheader("Add New Steel Coil")

        with st.form("add_coil_form"):
            col1, col2 = st.columns(2)

            with col1:
                saddle_types = manager.get_saddle_types()
                # Only show in-house production types
                in_house_types = {k: v for k, v in saddle_types.items() if v.get("in_house", True)}

                saddle_type = st.selectbox(
                    "Saddle Type *",
                    options=list(in_house_types.keys()),
                    format_func=lambda x: in_house_types[x]["name"],
                    help="Select what type of saddles this coil will produce"
                )

                colour = st.selectbox(
                    "Colour *",
                    options=sorted(manager.get_colours())
                )

                weight_kg = st.number_input(
                    "Weight (kg) *",
                    min_value=10.0,
                    max_value=600.0,
                    value=100.0,
                    step=5.0,
                    help="Coil weight in kilograms (typical: 50-500kg)"
                )

            with col2:
                supplier = st.selectbox(
                    "Supplier",
                    options=[""] + manager.get_suppliers(),
                    help="Where did this coil come from?"
                )

                received_date = st.date_input(
                    "Received Date",
                    value=datetime.now()
                )

                # Show estimate (note: updates on form submit, not live)
                estimate = manager.calculate_production_estimate(weight_kg, saddle_type)
                output_unit = estimate.get("output_unit", "saddles")
                st.markdown("### Estimated Yield")
                st.markdown(f"**Usable material:** {estimate['usable_kg']:.1f}kg")
                st.markdown(f"**Expected {output_unit}:** ~{estimate['expected_saddles']:,}")
                st.markdown(f"**Waste:** {estimate['waste_kg']:.1f}kg ({estimate['waste_percent']}%)")

            notes = st.text_area("Notes (optional)")

            submitted = st.form_submit_button("➕ Add Coil", type="primary")

            if submitted:
                try:
                    entry = manager.add_coil(
                        saddle_type=saddle_type,
                        colour=colour,
                        weight_kg=weight_kg,
                        supplier=supplier,
                        received_date=received_date.strftime("%Y-%m-%d"),
                        notes=notes
                    )
                    output_unit = in_house_types[saddle_type].get("output_unit", "saddles")
                    st.success(
                        f"✅ Added {weight_kg}kg {colour} coil for {in_house_types[saddle_type]['name']}!\n\n"
                        f"**Coil ID:** {entry['id']}\n\n"
                        f"**Estimated yield:** ~{entry['estimated_yield']:,} {output_unit}"
                    )
                    st.cache_resource.clear()
                except Exception as e:
                    st.error(f"Error adding coil: {e}")

    # -------------------------
    # TAB 3: Production Run
    # -------------------------
    with tab3:
        st.subheader("Log Production Run")
        st.info("Press saddles from a coil. This will deduct from the coil and add saddles to stock.")

        available_coils = manager.get_available_coils()

        if not available_coils:
            st.warning("No coils available for production. Add a coil first.")
        else:
            with st.form("production_form"):
                # Build coil options
                coil_options = []
                for coil in available_coils:
                    saddle_config = manager.get_saddle_types().get(coil["saddle_type"], {})
                    label = (
                        f"{coil['id']} - {saddle_config.get('name', coil['saddle_type'])} "
                        f"({coil['colour']}) - {coil['current_weight_kg']:.1f}kg remaining"
                    )
                    coil_options.append((label, coil))

                selected_coil_label = st.selectbox(
                    "Select Coil *",
                    options=[o[0] for o in coil_options]
                )

                # Find selected coil
                selected_coil = None
                for label, coil in coil_options:
                    if label == selected_coil_label:
                        selected_coil = coil
                        break

                col1, col2 = st.columns(2)

                with col1:
                    max_weight = selected_coil["current_weight_kg"] if selected_coil else 100
                    weight_used = st.number_input(
                        "Weight Used (kg) *",
                        min_value=0.5,
                        max_value=float(max_weight),
                        value=min(25.0, max_weight),
                        step=0.5,
                        help=f"Max available: {max_weight:.1f}kg"
                    )

                    # Show estimate with type-specific yields
                    if selected_coil:
                        estimate = manager.calculate_production_estimate(weight_used, selected_coil["saddle_type"])
                        output_unit = estimate.get("output_unit", "saddles")
                        st.markdown("### Expected Output")
                        st.markdown(f"**Usable:** {estimate['usable_kg']:.1f}kg")
                        st.markdown(f"**{output_unit.title()}:** ~{estimate['expected_saddles']:,}")
                        st.markdown(f"**Waste:** {estimate['waste_kg']:.1f}kg")

                with col2:
                    # Allow override of actual count
                    estimate = manager.calculate_production_estimate(weight_used, selected_coil["saddle_type"]) if selected_coil else {"expected_saddles": 0, "output_unit": "saddles"}
                    output_unit = estimate.get("output_unit", "saddles")
                    actual_saddles = st.number_input(
                        f"Actual {output_unit.title()} Produced",
                        min_value=0,
                        max_value=100000,
                        value=estimate["expected_saddles"],
                        help="Override if actual count differs from estimate"
                    )

                    operator = st.text_input("Operator Name")

                notes = st.text_area("Notes (optional)")

                submitted = st.form_submit_button("⚙️ Log Production", type="primary")

                if submitted and selected_coil:
                    try:
                        record = manager.log_production(
                            coil_id=selected_coil["id"],
                            weight_used_kg=weight_used,
                            saddles_produced=actual_saddles if actual_saddles > 0 else None,
                            operator=operator,
                            notes=notes
                        )

                        remaining = selected_coil["current_weight_kg"] - weight_used
                        type_config = manager.get_saddle_types().get(selected_coil["saddle_type"], {})
                        output_unit = type_config.get("output_unit", "saddles")

                        st.success(
                            f"✅ Production logged!\n\n"
                            f"**{output_unit.title()} produced:** {record['saddles_produced']:,}\n\n"
                            f"**Waste:** {record['waste_kg']:.1f}kg\n\n"
                            f"**Coil remaining:** {remaining:.1f}kg"
                        )
                        st.balloons()
                        st.cache_resource.clear()

                    except ValueError as e:
                        st.error(f"Error: {e}")
                    except Exception as e:
                        st.error(f"Unexpected error: {e}")

    # -------------------------
    # TAB 4: Production History
    # -------------------------
    with tab4:
        st.subheader("Recent Production Runs")

        history = manager.get_production_history(days=90)

        if history:
            for record in history:
                saddle_config = manager.get_saddle_types().get(record["saddle_type"], {})

                with st.expander(
                    f"{record['date'][:10]} - {saddle_config.get('name', record['saddle_type'])} "
                    f"({record['colour']}) - {record['saddles_produced']:,} saddles"
                ):
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.write("**Input:**")
                        st.write(f"  Coil ID: {record['coil_id']}")
                        st.write(f"  Weight used: {record['weight_used_kg']:.1f}kg")

                    with col2:
                        st.write("**Output:**")
                        st.write(f"  Usable: {record['usable_kg']:.1f}kg")
                        st.write(f"  Saddles: {record['saddles_produced']:,}")
                        st.write(f"  Expected: {record['expected_saddles']:,}")

                    with col3:
                        st.write("**Waste:**")
                        st.write(f"  {record['waste_kg']:.1f}kg")

                        variance = record['saddles_produced'] - record['expected_saddles']
                        if variance != 0:
                            st.write(f"  Variance: {variance:+,}")

                    if record.get("operator"):
                        st.write(f"**Operator:** {record['operator']}")
                    if record.get("notes"):
                        st.write(f"**Notes:** {record['notes']}")
        else:
            st.info("No production runs recorded yet.")


if __name__ == "__main__":
    main()
