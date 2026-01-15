"""
Gutter Guard Warehouse - Inventory Dashboard

Main Streamlit application for inventory tracking.
"""

import streamlit as st
import sys
import os
import json
from datetime import datetime
import uuid

from dotenv import load_dotenv
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mesh_manager import MeshManager
from core.forecasting import Forecaster

# Page configuration
st.set_page_config(
    page_title="GGW Inventory",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)


def get_app_password() -> str:
    """Get app password from environment or Streamlit secrets."""
    password = os.getenv("APP_PASSWORD", "")
    if password:
        return password
    try:
        return st.secrets.get("APP_PASSWORD", "")
    except Exception:
        return ""


def check_password() -> bool:
    """Check if user has entered correct password."""
    if st.session_state.get("authenticated"):
        return True

    st.title("🔐 GGW Inventory")
    st.markdown("Please enter the password to access the dashboard.")

    password = st.text_input("Password", type="password", key="password_input")

    if st.button("Login", type="primary"):
        if password == get_app_password():
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")

    return False

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUGGESTIONS_PATH = os.path.join(BASE_DIR, "data", "suggestions.json")


def load_suggestions():
    """Load suggestions from file."""
    try:
        with open(SUGGESTIONS_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"suggestions": []}


def save_suggestion(staff_name: str, suggestion_text: str, page: str = "Home"):
    """Save a new suggestion."""
    data = load_suggestions()
    data["suggestions"].append({
        "id": str(uuid.uuid4())[:8],
        "date": datetime.utcnow().isoformat() + "Z",
        "staff_name": staff_name,
        "page": page,
        "suggestion": suggestion_text,
        "status": "pending"
    })
    with open(SUGGESTIONS_PATH, "w") as f:
        json.dump(data, f, indent=2)


# Initialize managers
@st.cache_resource
def get_managers():
    return MeshManager(), Forecaster()

mesh_manager, forecaster = get_managers()


def main():
    # Check password before showing anything
    if not check_password():
        return

    st.title("🏠 Gutter Guard Warehouse")
    st.subheader("Inventory Dashboard")

    # Reload data button
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_resource.clear()
        st.rerun()

    # Staff suggestions widget
    st.sidebar.markdown("---")
    with st.sidebar.expander("💡 Suggestions"):
        suggestions_data = load_suggestions()
        pending_count = len([s for s in suggestions_data.get("suggestions", []) if s.get("status") == "pending"])

        if pending_count > 0:
            st.caption(f"{pending_count} pending suggestion(s)")

        with st.form("suggestion_form", clear_on_submit=True):
            staff_name = st.text_input("Your Name", placeholder="e.g. John")
            suggestion_text = st.text_area("Suggestion", placeholder="What would you like to change?", height=80)
            submitted = st.form_submit_button("Submit")

            if submitted and staff_name and suggestion_text:
                save_suggestion(staff_name, suggestion_text)
                st.success("Thanks! Suggestion saved.")
                st.rerun()

    # Summary stats
    stats = forecaster.get_summary_stats()

    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="📦 Total Mesh Stock",
            value=f"{stats['total_rolls']} rolls",
            help="Total mesh rolls in inventory"
        )

    with col2:
        st.metric(
            label="📏 Total Metres",
            value=f"{stats['total_metres']:,.0f}m",
            help="Total metres of mesh in stock"
        )

    with col3:
        delta_color = "inverse" if stats['critical_items'] > 0 else "off"
        st.metric(
            label="⚠️ Critical Items",
            value=stats['critical_items'],
            delta="Needs Order!" if stats['critical_items'] > 0 else None,
            delta_color=delta_color
        )

    with col4:
        st.metric(
            label="📉 Low Stock",
            value=stats['low_stock_items'],
            help="Items with less than 5 months stock"
        )

    st.divider()

    # Alerts section
    forecasts = forecaster.calculate_stock_forecast()
    critical = [f for f in forecasts if f["status"] in ["CRITICAL", "ORDER_NOW"]]

    if critical:
        st.error("### ⚠️ Critical Stock Alerts")
        st.warning(
            "**REMINDER:** Mesh has a 4-month lead time. "
            "Order now to avoid stockouts!"
        )

        for item in critical:
            months = item["months_remaining"]
            months_str = f"{months:.1f} months" if months else "Unknown"

            st.error(
                f"**{item['mesh_name']}** - {item['width_mm']}mm - {item['colour']}: "
                f"Only {item['current_metres']:.0f}m remaining ({months_str})"
            )

    # Stock overview table
    st.subheader("📊 Current Stock Overview")

    if forecasts:
        # Create display table
        table_data = []
        for f in forecasts:
            status_emoji = {
                "OK": "✅",
                "LOW": "🟡",
                "ORDER_NOW": "🟠",
                "CRITICAL": "🔴",
                "NO_USAGE": "⚪"
            }.get(f["status"], "")

            table_data.append({
                "Status": f"{status_emoji} {f['status']}",
                "Mesh Type": f["mesh_name"],
                "Width": f"{f['width_mm']}mm",
                "Colour": f["colour"],
                "Stock (m)": f"{f['current_metres']:.0f}",
                "Daily Usage": f"{f['avg_daily_usage']:.1f}m/day",
                "Days Left": f"{f['days_remaining']:.0f}" if f["days_remaining"] else "-",
                "Months Left": f"{f['months_remaining']:.1f}" if f["months_remaining"] else "-"
            })

        st.dataframe(
            table_data,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No inventory data yet. Add stock using the Mesh Rolls page.")

    # Usage chart
    st.subheader("📈 Usage History (Last 6 Months)")

    usage_by_month = forecaster.get_usage_by_period(180, "month")
    if usage_by_month:
        st.bar_chart(usage_by_month)
    else:
        st.info("No usage data yet. Usage will be tracked as orders are fulfilled.")

    # Reorder suggestions
    suggestions = forecaster.get_reorder_suggestions()
    if suggestions:
        st.subheader("📋 Reorder Suggestions")

        for s in suggestions:
            urgency_color = {
                "CRITICAL": "🔴",
                "ORDER_NOW": "🟠",
                "LOW": "🟡"
            }.get(s["urgency"], "")

            st.warning(
                f"{urgency_color} **{s['mesh_name']}** - {s['width_mm']}mm - {s['colour']}\n\n"
                f"Current: {s['current_metres']:.0f}m | "
                f"Suggested Order: **{s['suggested_order_metres']:.0f}m**"
            )

    # Footer
    st.divider()
    st.caption(f"Last updated: {stats['last_updated'] or 'Never'}")
    st.caption("Mesh lead time: 4 months | Alert threshold: 5 months stock")


if __name__ == "__main__":
    main()
