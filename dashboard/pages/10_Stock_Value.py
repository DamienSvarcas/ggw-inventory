"""
Stock Value Dashboard - Password Protected

View total stock value across all inventory categories.
Requires password authentication to access.
"""

import streamlit as st
import json
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
ENV_PATH = Path(__file__).parent.parent.parent / ".env"
load_dotenv(ENV_PATH)

# Paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"
PRICING_PATH = DATA_DIR / "pricing.json"

st.set_page_config(page_title="Stock Value", page_icon="💰", layout="wide")


def load_pricing() -> dict:
    """Load pricing configuration."""
    try:
        with open(PRICING_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "last_updated": None,
            "mesh": {
                "4mm_aluminium": {"price_per_metre": 0, "notes": ""},
                "2mm_ember_guard": {"price_per_metre": 0, "notes": ""}
            },
            "screws": {"price_per_box": 0, "box_size": 1000},
            "saddles": {
                "corrugated": {"price_each": 0},
                "trimdek": {"price_each": 0}
            },
            "trims": {"price_each": 0},
            "boxes": {
                "small_tube": {"price_each": 0},
                "large_tube": {"price_each": 0},
                "saddle_box": {"price_each": 0}
            },
            "coils": {"price_per_kg": 0}
        }


def save_pricing(pricing: dict):
    """Save pricing configuration."""
    pricing["last_updated"] = datetime.utcnow().isoformat() + "Z"
    with open(PRICING_PATH, "w") as f:
        json.dump(pricing, f, indent=2)


def load_data_file(filename: str) -> dict:
    """Load a data file."""
    filepath = DATA_DIR / filename
    if filepath.exists():
        with open(filepath, "r") as f:
            return json.load(f)
    return {}


def get_password() -> str:
    """Get password from environment variable or Streamlit secrets."""
    # Try environment variable first (local development)
    password = os.getenv("STOCK_VALUE_PASSWORD", "")
    if password:
        return password
    # Fall back to Streamlit secrets (cloud deployment)
    try:
        return st.secrets.get("STOCK_VALUE_PASSWORD", "")
    except Exception:
        return ""


def check_password() -> bool:
    """Check if the entered password is correct."""
    correct_password = get_password()

    if not correct_password:
        st.error("Password not configured. Please set STOCK_VALUE_PASSWORD in .env file or Streamlit secrets.")
        return False

    if "stock_value_authenticated" not in st.session_state:
        st.session_state.stock_value_authenticated = False

    if st.session_state.stock_value_authenticated:
        return True

    return False


def calculate_mesh_value(pricing: dict) -> tuple:
    """Calculate total mesh value and line items."""
    data = load_data_file("mesh_rolls.json")
    inventory = data.get("inventory", [])

    total = 0.0
    items = []

    for item in inventory:
        mesh_type = item.get("mesh_type", "")
        price_per_m = pricing.get("mesh", {}).get(mesh_type, {}).get("price_per_metre", 0)
        qty = item.get("quantity", 0)
        length = item.get("length_m", 0)
        total_metres = qty * length
        line_total = total_metres * price_per_m
        total += line_total

        items.append({
            "description": f"{mesh_type} - {item.get('width_mm')}mm x {length}m - {item.get('colour')}",
            "quantity": qty,
            "unit": "rolls",
            "metres": total_metres,
            "unit_price": price_per_m,
            "total": line_total
        })

    return total, items


def calculate_screw_value(pricing: dict) -> tuple:
    """Calculate total screw value and line items."""
    data = load_data_file("screw_inventory.json")
    inventory = data.get("inventory", [])

    total = 0.0
    items = []
    price_per_box = pricing.get("screws", {}).get("price_per_box", 0)
    box_size = pricing.get("screws", {}).get("box_size", 1000)

    for item in inventory:
        qty = item.get("quantity", 0)
        # Convert screws to boxes
        boxes = qty / box_size if box_size > 0 else 0
        line_total = boxes * price_per_box
        total += line_total

        items.append({
            "description": f"Screws - {item.get('colour')}",
            "quantity": qty,
            "unit": "screws",
            "boxes": boxes,
            "unit_price": price_per_box,
            "total": line_total
        })

    return total, items


def calculate_saddle_value(pricing: dict) -> tuple:
    """Calculate total saddle value and line items."""
    data = load_data_file("saddle_stock.json")
    inventory = data.get("inventory", [])

    total = 0.0
    items = []

    for item in inventory:
        saddle_type = item.get("saddle_type", "")
        price_each = pricing.get("saddles", {}).get(saddle_type, {}).get("price_each", 0)
        qty = item.get("quantity", 0)
        line_total = qty * price_each
        total += line_total

        type_name = "Corrugated" if saddle_type == "corrugated" else "Trimdek"
        items.append({
            "description": f"{type_name} Saddles - {item.get('colour')}",
            "quantity": qty,
            "unit": "saddles",
            "unit_price": price_each,
            "total": line_total
        })

    return total, items


def calculate_trim_value(pricing: dict) -> tuple:
    """Calculate total trim value and line items."""
    data = load_data_file("trim_inventory.json")
    inventory = data.get("inventory", [])

    total = 0.0
    items = []
    price_each = pricing.get("trims", {}).get("price_each", 0) if isinstance(pricing.get("trims"), dict) else pricing.get("trims", 0)

    for item in inventory:
        qty = item.get("quantity", 0)
        line_total = qty * price_each
        total += line_total

        items.append({
            "description": f"Trims - {item.get('colour')}",
            "quantity": qty,
            "unit": "trims",
            "unit_price": price_each,
            "total": line_total
        })

    return total, items


def calculate_box_value(pricing: dict) -> tuple:
    """Calculate total box value and line items."""
    data = load_data_file("box_inventory.json")
    inventory = data.get("inventory", [])

    total = 0.0
    items = []

    box_names = {
        "small_tube": "Small Tube",
        "large_tube": "Large Tube",
        "saddle_box": "Saddle Box"
    }

    for item in inventory:
        box_type = item.get("box_type", "")
        price_each = pricing.get("boxes", {}).get(box_type, {}).get("price_each", 0)
        qty = item.get("quantity", 0)
        line_total = qty * price_each
        total += line_total

        items.append({
            "description": f"Boxes - {box_names.get(box_type, box_type)}",
            "quantity": qty,
            "unit": "boxes",
            "unit_price": price_each,
            "total": line_total
        })

    return total, items


def calculate_coil_value(pricing: dict) -> tuple:
    """Calculate total coil value and line items."""
    data = load_data_file("coil_inventory.json")
    inventory = data.get("inventory", [])

    total = 0.0
    items = []
    price_per_kg = pricing.get("coils", {}).get("price_per_kg", 0) if isinstance(pricing.get("coils"), dict) else pricing.get("coils", 0)

    for item in inventory:
        weight = item.get("current_weight_kg", 0)
        line_total = weight * price_per_kg
        total += line_total

        saddle_type = item.get("saddle_type", "")
        type_name = "Corrugated" if saddle_type == "corrugated" else "Trim" if saddle_type == "trim" else saddle_type
        items.append({
            "description": f"Coil ({type_name}) - {item.get('colour')}",
            "quantity": weight,
            "unit": "kg",
            "unit_price": price_per_kg,
            "total": line_total
        })

    return total, items


def render_password_screen():
    """Render the password entry screen."""
    st.title("Stock Value Dashboard")
    st.markdown("---")

    st.warning("This page requires authentication.")

    with st.form("password_form"):
        password = st.text_input("Enter Password", type="password")
        submitted = st.form_submit_button("Unlock", type="primary")

        if submitted:
            correct_password = get_password()
            if password == correct_password:
                st.session_state.stock_value_authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password. Access denied.")


def render_dashboard():
    """Render the main stock value dashboard."""
    st.title("Stock Value Dashboard")

    # Lock button in sidebar
    if st.sidebar.button("Lock Dashboard"):
        st.session_state.stock_value_authenticated = False
        st.rerun()

    # Load pricing
    pricing = load_pricing()

    # Calculate all values
    mesh_total, mesh_items = calculate_mesh_value(pricing)
    screw_total, screw_items = calculate_screw_value(pricing)
    saddle_total, saddle_items = calculate_saddle_value(pricing)
    trim_total, trim_items = calculate_trim_value(pricing)
    box_total, box_items = calculate_box_value(pricing)
    coil_total, coil_items = calculate_coil_value(pricing)

    grand_total = mesh_total + screw_total + saddle_total + trim_total + box_total + coil_total

    # Grand Total Header
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
                padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
        <h2 style="color: #ffffff; margin: 0; font-size: 1.2em;">TOTAL STOCK VALUE</h2>
        <h1 style="color: #ffffff; margin: 10px 0 0 0; font-size: 3em;">${:,.2f}</h1>
    </div>
    """.format(grand_total), unsafe_allow_html=True)

    # Price Editor
    with st.expander("Edit Unit Prices", expanded=False):
        st.info("Set the unit prices for each item type. These prices are used to calculate stock values.")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Mesh")
            mesh_4mm_price = st.number_input(
                "4mm Aluminium ($/metre)",
                min_value=0.0,
                value=float(pricing.get("mesh", {}).get("4mm_aluminium", {}).get("price_per_metre", 0)),
                step=0.01,
                format="%.2f",
                key="mesh_4mm_price"
            )

            mesh_2mm_price = st.number_input(
                "2mm Ember Guard ($/metre)",
                min_value=0.0,
                value=float(pricing.get("mesh", {}).get("2mm_ember_guard", {}).get("price_per_metre", 0)),
                step=0.01,
                format="%.2f",
                key="mesh_2mm_price"
            )

            st.subheader("Screws")
            screw_price = st.number_input(
                "Price per box of 1000 ($)",
                min_value=0.0,
                value=float(pricing.get("screws", {}).get("price_per_box", 0)),
                step=0.01,
                format="%.2f",
                key="screw_price"
            )

            st.subheader("Trims")
            trim_price = st.number_input(
                "Price per trim ($)",
                min_value=0.0,
                value=float(pricing.get("trims", 0) if isinstance(pricing.get("trims"), (int, float)) else pricing.get("trims", {}).get("price_each", 0)),
                step=0.01,
                format="%.2f",
                key="trim_price"
            )

        with col2:
            st.subheader("Saddles")
            corr_saddle_price = st.number_input(
                "Corrugated ($/each)",
                min_value=0.0,
                value=float(pricing.get("saddles", {}).get("corrugated", {}).get("price_each", 0)),
                step=0.01,
                format="%.2f",
                key="corr_saddle_price"
            )

            trimdek_saddle_price = st.number_input(
                "Trimdek ($/each)",
                min_value=0.0,
                value=float(pricing.get("saddles", {}).get("trimdek", {}).get("price_each", 0)),
                step=0.01,
                format="%.2f",
                key="trimdek_saddle_price"
            )

            st.subheader("Boxes")
            small_tube_price = st.number_input(
                "Small Tube ($/each)",
                min_value=0.0,
                value=float(pricing.get("boxes", {}).get("small_tube", {}).get("price_each", 0)),
                step=0.01,
                format="%.2f",
                key="small_tube_price"
            )

            large_tube_price = st.number_input(
                "Large Tube ($/each)",
                min_value=0.0,
                value=float(pricing.get("boxes", {}).get("large_tube", {}).get("price_each", 0)),
                step=0.01,
                format="%.2f",
                key="large_tube_price"
            )

            saddle_box_price = st.number_input(
                "Saddle Box ($/each)",
                min_value=0.0,
                value=float(pricing.get("boxes", {}).get("saddle_box", {}).get("price_each", 0)),
                step=0.01,
                format="%.2f",
                key="saddle_box_price"
            )

            st.subheader("Raw Coils")
            coil_price = st.number_input(
                "Price per kg ($)",
                min_value=0.0,
                value=float(pricing.get("coils", 0) if isinstance(pricing.get("coils"), (int, float)) else pricing.get("coils", {}).get("price_per_kg", 0)),
                step=0.01,
                format="%.2f",
                key="coil_price"
            )

        if st.button("Save Prices", type="primary"):
            new_pricing = {
                "mesh": {
                    "4mm_aluminium": {"price_per_metre": mesh_4mm_price, "notes": ""},
                    "2mm_ember_guard": {"price_per_metre": mesh_2mm_price, "notes": ""}
                },
                "screws": {"price_per_box": screw_price, "box_size": 1000},
                "saddles": {
                    "corrugated": {"price_each": corr_saddle_price},
                    "trimdek": {"price_each": trimdek_saddle_price}
                },
                "trims": {"price_each": trim_price},
                "boxes": {
                    "small_tube": {"price_each": small_tube_price},
                    "large_tube": {"price_each": large_tube_price},
                    "saddle_box": {"price_each": saddle_box_price}
                },
                "coils": {"price_per_kg": coil_price}
            }
            save_pricing(new_pricing)
            st.success("Prices saved successfully!")
            st.rerun()

    st.markdown("---")

    # Category Breakdown
    st.subheader("Value by Category")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Mesh Rolls", f"${mesh_total:,.2f}")
        st.metric("Screws", f"${screw_total:,.2f}")

    with col2:
        st.metric("Corrugated Saddles", f"${saddle_total:,.2f}")
        st.metric("Trims", f"${trim_total:,.2f}")

    with col3:
        st.metric("Boxes", f"${box_total:,.2f}")
        st.metric("Raw Coils", f"${coil_total:,.2f}")

    with col4:
        # Show percentage breakdown
        if grand_total > 0:
            st.caption("% of Total")
            st.caption(f"Mesh: {mesh_total/grand_total*100:.1f}%")
            st.caption(f"Screws: {screw_total/grand_total*100:.1f}%")
            st.caption(f"Saddles: {saddle_total/grand_total*100:.1f}%")
            st.caption(f"Trims: {trim_total/grand_total*100:.1f}%")
            st.caption(f"Boxes: {box_total/grand_total*100:.1f}%")
            st.caption(f"Coils: {coil_total/grand_total*100:.1f}%")

    st.markdown("---")

    # Detailed Breakdown Tables
    st.subheader("Detailed Breakdown")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        f"Mesh (${mesh_total:,.2f})",
        f"Screws (${screw_total:,.2f})",
        f"Saddles (${saddle_total:,.2f})",
        f"Trims (${trim_total:,.2f})",
        f"Boxes (${box_total:,.2f})",
        f"Coils (${coil_total:,.2f})"
    ])

    with tab1:
        if mesh_items:
            for item in mesh_items:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(item["description"])
                with col2:
                    st.write(f"{item['quantity']} rolls ({item['metres']}m)")
                with col3:
                    st.write(f"${item['total']:,.2f}")
        else:
            st.info("No mesh inventory.")

    with tab2:
        if screw_items:
            for item in screw_items:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(item["description"])
                with col2:
                    st.write(f"{item['quantity']:,} screws ({item['boxes']:.1f} boxes)")
                with col3:
                    st.write(f"${item['total']:,.2f}")
        else:
            st.info("No screw inventory.")

    with tab3:
        if saddle_items:
            for item in saddle_items:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(item["description"])
                with col2:
                    st.write(f"{item['quantity']:,} {item['unit']}")
                with col3:
                    st.write(f"${item['total']:,.2f}")
        else:
            st.info("No saddle inventory.")

    with tab4:
        if trim_items:
            for item in trim_items:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(item["description"])
                with col2:
                    st.write(f"{item['quantity']:,} {item['unit']}")
                with col3:
                    st.write(f"${item['total']:,.2f}")
        else:
            st.info("No trim inventory.")

    with tab5:
        if box_items:
            for item in box_items:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(item["description"])
                with col2:
                    st.write(f"{item['quantity']:,} {item['unit']}")
                with col3:
                    st.write(f"${item['total']:,.2f}")
        else:
            st.info("No box inventory.")

    with tab6:
        if coil_items:
            for item in coil_items:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(item["description"])
                with col2:
                    st.write(f"{item['quantity']:.1f} {item['unit']}")
                with col3:
                    st.write(f"${item['total']:,.2f}")
        else:
            st.info("No coil inventory.")

    # Footer
    st.markdown("---")
    last_updated = pricing.get("last_updated")
    if last_updated:
        st.caption(f"Prices last updated: {last_updated}")
    else:
        st.caption("Prices not yet configured - edit prices above to set unit costs.")


def main():
    # Initialize session state
    if "stock_value_authenticated" not in st.session_state:
        st.session_state.stock_value_authenticated = False

    # Check if password is configured
    if not get_password():
        st.error("Stock Value Dashboard is not configured. Please set STOCK_VALUE_PASSWORD in .env file or Streamlit secrets.")
        return

    # Show appropriate screen
    if st.session_state.stock_value_authenticated:
        render_dashboard()
    else:
        render_password_screen()


if __name__ == "__main__":
    main()
