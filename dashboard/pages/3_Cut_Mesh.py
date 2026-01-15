"""
Cut Mesh Page

Cut wide mesh rolls into smaller widths.
"""

import streamlit as st
import sys
import os

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.mesh_manager import MeshManager

st.set_page_config(page_title="Cut Mesh", page_icon="✂️", layout="wide")

# Initialize manager
@st.cache_resource
def get_manager():
    return MeshManager()

manager = get_manager()


def main():
    st.title("✂️ Cut Mesh Rolls")
    st.info(
        "Cut wide mesh rolls (1000mm, 750mm, 500mm) into smaller widths "
        "when you run out of smaller rolls."
    )

    # Refresh button
    if st.sidebar.button("🔄 Refresh"):
        st.cache_resource.clear()
        st.rerun()

    # Tabs
    tab1, tab2 = st.tabs(["✂️ Cut Roll", "📜 Cutting History"])

    # -------------------------
    # TAB 1: Cut Roll
    # -------------------------
    with tab1:
        st.subheader("Cut a Roll")

        # Get inventory of cuttable rolls (500mm, 750mm, 1000mm)
        summary = manager.get_inventory_summary()
        cuttable = [
            s for s in summary
            if s["width_mm"] in [500, 750, 1000] and s["quantity"] > 0
        ]

        if not cuttable:
            st.warning(
                "No cuttable rolls in stock. "
                "You need 500mm, 750mm, or 1000mm rolls to cut."
            )
        else:
            with st.form("cut_form"):
                # Build selection options
                options = []
                for item in cuttable:
                    mesh_config = manager.get_mesh_types().get(item["mesh_type"], {})
                    label = (
                        f"{mesh_config.get('name', item['mesh_type'])} - "
                        f"{item['width_mm']}mm x {item['length_m']}m - "
                        f"{item['colour']} ({item['quantity']} available)"
                    )
                    options.append((label, item))

                selected_label = st.selectbox(
                    "Select Roll to Cut *",
                    options=[o[0] for o in options]
                )

                # Find selected item
                selected_item = None
                for label, item in options:
                    if label == selected_label:
                        selected_item = item
                        break

                # Show cutting options based on selected width
                if selected_item:
                    cutting_options = manager.get_cutting_options(selected_item["width_mm"])

                    if cutting_options:
                        cut_choice = st.selectbox(
                            "How to cut? *",
                            options=[o["label"] for o in cutting_options],
                            help="Select how to divide the roll"
                        )

                        # Find selected cutting option
                        selected_cut = None
                        for opt in cutting_options:
                            if opt["label"] == cut_choice:
                                selected_cut = opt
                                break

                        # Preview
                        if selected_cut:
                            st.info(
                                f"**Preview:** 1x {selected_item['width_mm']}mm → "
                                f"{selected_cut['label']} (each {selected_item['length_m']}m long)"
                            )
                    else:
                        st.warning("No cutting options available for this width.")
                        selected_cut = None

                col1, col2 = st.columns(2)
                with col1:
                    operator = st.text_input("Operator Name")
                with col2:
                    notes = st.text_input("Notes (optional)")

                submitted = st.form_submit_button("✂️ Cut Roll", type="primary")

                if submitted and selected_item and selected_cut:
                    try:
                        result = manager.cut_roll(
                            mesh_type=selected_item["mesh_type"],
                            source_width_mm=selected_item["width_mm"],
                            length_m=selected_item["length_m"],
                            colour=selected_item["colour"],
                            target_widths=selected_cut["widths"],
                            operator=operator,
                            notes=notes
                        )

                        st.success(
                            f"✅ Successfully cut 1x {selected_item['width_mm']}mm roll into "
                            f"{selected_cut['label']}!"
                        )

                        # Show result details
                        st.write("**Created rolls:**")
                        for r in result["result"]:
                            st.write(f"  • {r['quantity']}x {r['width_mm']}mm x {selected_item['length_m']}m")

                        st.cache_resource.clear()

                    except ValueError as e:
                        st.error(f"Error: {e}")
                    except Exception as e:
                        st.error(f"Unexpected error: {e}")

    # -------------------------
    # TAB 2: Cutting History
    # -------------------------
    with tab2:
        st.subheader("Recent Cutting Operations")

        history = manager.get_cutting_history(days=90)

        if history:
            for record in history:
                mesh_config = manager.get_mesh_types().get(record["mesh_type"], {})
                mesh_name = mesh_config.get("name", record["mesh_type"])

                # Format result
                result_str = ", ".join(
                    f"{r['quantity']}x {r['width_mm']}mm"
                    for r in record["result"]
                )

                with st.expander(
                    f"{record['date'][:10]} - {mesh_name} {record['source']['colour']}"
                ):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write("**Source Roll:**")
                        st.write(
                            f"  {record['source']['width_mm']}mm x "
                            f"{record['source']['length_m']}m - "
                            f"{record['source']['colour']}"
                        )

                    with col2:
                        st.write("**Result:**")
                        st.write(f"  {result_str}")

                    if record.get("operator"):
                        st.write(f"**Operator:** {record['operator']}")
                    if record.get("notes"):
                        st.write(f"**Notes:** {record['notes']}")
        else:
            st.info("No cutting operations recorded yet.")


if __name__ == "__main__":
    main()
