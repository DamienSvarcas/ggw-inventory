"""
Forecasting Page

View usage trends and stock predictions for all inventory types.
Integrates with Shopify orders for component usage analysis.
"""

import streamlit as st
import sys
import os

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.forecasting import Forecaster
from core.mesh_manager import MeshManager

st.set_page_config(page_title="Forecasting", page_icon="📈", layout="wide")

# Initialize
@st.cache_resource
def get_forecaster():
    return Forecaster(), MeshManager()

forecaster, manager = get_forecaster()


def main():
    st.title("📈 Forecasting & Usage Analysis")

    # Refresh button
    if st.sidebar.button("🔄 Refresh"):
        st.cache_resource.clear()
        st.rerun()

    # Shopify sync status
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Shopify Data")
    try:
        usage = forecaster.get_shopify_usage()
        st.sidebar.metric("Orders Analyzed", f"{usage.get('order_count', 0):,}")
        st.sidebar.metric("Period", f"{usage.get('period_days', 0)} days")
        if usage.get("order_count", 0) > 0:
            st.sidebar.success("Connected")
        else:
            st.sidebar.warning("No orders found")
    except Exception as e:
        st.sidebar.error("Sync error")

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📦 Mesh Forecast",
        "🔩 Component Forecast",
        "📉 Usage Trends",
        "📋 Reorder Suggestions",
        "📊 Shopify Usage"
    ])

    # -------------------------
    # TAB 1: Mesh Stock Forecast
    # -------------------------
    with tab1:
        st.subheader("Mesh Stock Forecast")
        st.info("⏰ **Reminder:** Mesh has a 4-month lead time. Plan ahead!")

        forecasts = forecaster.calculate_stock_forecast()

        if forecasts:
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)

            critical = len([f for f in forecasts if f["status"] == "CRITICAL"])
            order_now = len([f for f in forecasts if f["status"] == "ORDER_NOW"])
            low = len([f for f in forecasts if f["status"] == "LOW"])
            ok = len([f for f in forecasts if f["status"] == "OK"])

            with col1:
                st.metric("🔴 Critical", critical)
            with col2:
                st.metric("🟠 Order Now", order_now)
            with col3:
                st.metric("🟡 Low Stock", low)
            with col4:
                st.metric("✅ OK", ok)

            st.divider()

            # Filter by status
            status_filter = st.multiselect(
                "Filter by Status",
                options=["CRITICAL", "ORDER_NOW", "LOW", "OK", "NO_USAGE"],
                default=["CRITICAL", "ORDER_NOW", "LOW", "OK"]
            )

            filtered = [f for f in forecasts if f["status"] in status_filter]

            # Display table
            if filtered:
                table_data = []
                for f in filtered:
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
                        "Current Stock": f"{f['current_metres']:.0f}m",
                        "Daily Usage": f"{f['avg_daily_usage']:.2f}m",
                        "Monthly Usage": f"{f['avg_monthly_usage']:.0f}m",
                        "Days Left": f"{f['days_remaining']:.0f}" if f["days_remaining"] else "∞",
                        "Months Left": f"{f['months_remaining']:.1f}" if f["months_remaining"] else "∞",
                        "Lead Time": f"{f['lead_time_months']} months"
                    })

                st.dataframe(table_data, use_container_width=True, hide_index=True)
            else:
                st.info("No items match your filter.")
        else:
            st.info("No data available for forecasting yet.")

    # -------------------------
    # TAB 2: Component Forecast
    # -------------------------
    with tab2:
        st.subheader("Component Forecast (Shopify-based)")
        st.caption("Usage calculated from last 6 months of Shopify orders")

        component_forecast = forecaster.get_component_forecast()

        # Saddles
        st.markdown("### Saddles & Trims")

        saddle_forecasts = component_forecast.get("saddles", [])
        trim_forecasts = component_forecast.get("trims", [])

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Saddle Stock**")
            if saddle_forecasts:
                for f in saddle_forecasts:
                    status_emoji = _get_status_emoji(f.get("status", ""))
                    label = f.get("saddle_type", "Unknown").replace("_", " ").title()
                    colour = f.get("colour", "")

                    if f.get("type") == "coil_yield":
                        st.markdown(
                            f"- {status_emoji} **{label}** ({colour}): "
                            f"~{f['current_qty']:,} from {f.get('coil_weight_kg', 0):.1f}kg coil"
                        )
                    else:
                        days_left = f.get("days_remaining")
                        days_text = f"{days_left:.0f} days" if days_left else "∞"
                        st.markdown(
                            f"- {status_emoji} **{label}** ({colour}): "
                            f"{f['current_qty']:,} ({days_text})"
                        )
            else:
                st.info("No saddle stock data")

        with col2:
            st.markdown("**Trim Stock**")
            if trim_forecasts:
                for f in trim_forecasts:
                    status_emoji = _get_status_emoji(f.get("status", ""))
                    colour = f.get("colour", "Unknown")

                    if f.get("type") == "coil_yield":
                        st.markdown(
                            f"- {status_emoji} **Trims** ({colour}): "
                            f"~{f['current_qty']:,} from {f.get('coil_weight_kg', 0):.1f}kg coil"
                        )
                    else:
                        days_left = f.get("days_remaining")
                        days_text = f"{days_left:.0f} days" if days_left else "∞"
                        st.markdown(
                            f"- {status_emoji} **Trims** ({colour}): "
                            f"{f['current_qty']:,} ({days_text})"
                        )
            else:
                st.info("No trim stock data")

        st.divider()

        # Screws
        st.markdown("### Screws")

        screw_forecasts = component_forecast.get("screws", [])

        if screw_forecasts:
            table_data = []
            for f in screw_forecasts:
                status_emoji = _get_status_emoji(f.get("status", ""))
                table_data.append({
                    "Status": f"{status_emoji} {f.get('status', '')}",
                    "Type": f.get("screw_name", f.get("screw_type", "")),
                    "Colour": f.get("colour", ""),
                    "Current Qty": f"{f['current_qty']:,}",
                    "Daily Usage": f"{f['daily_usage']:.1f}",
                    "Days Left": f"{f['days_remaining']:.0f}" if f.get("days_remaining") else "∞"
                })

            st.dataframe(table_data, use_container_width=True, hide_index=True)
        else:
            st.info("No screw stock data. Add screws on the Screws page.")

        st.divider()

        # Boxes
        st.markdown("### Boxes")

        box_forecasts = component_forecast.get("boxes", [])

        if box_forecasts:
            table_data = []
            for f in box_forecasts:
                status_emoji = _get_status_emoji(f.get("status", ""))
                table_data.append({
                    "Status": f"{status_emoji} {f.get('status', '')}",
                    "Type": f.get("box_name", f.get("box_type", "")),
                    "Current Qty": f"{f['current_qty']:,}",
                    "Daily Usage": f"{f['daily_usage']:.1f}",
                    "Days Left": f"{f['days_remaining']:.0f}" if f.get("days_remaining") else "∞"
                })

            st.dataframe(table_data, use_container_width=True, hide_index=True)
        else:
            st.info("No box stock data. Add boxes on the Boxes page.")

    # -------------------------
    # TAB 3: Usage Trends
    # -------------------------
    with tab3:
        st.subheader("Usage Trends")

        col1, col2 = st.columns([1, 3])

        with col1:
            period = st.selectbox(
                "Group By",
                options=["week", "month"],
                index=1
            )

            days = st.slider(
                "Analysis Period (days)",
                min_value=30,
                max_value=365,
                value=180,
                step=30
            )

        with col2:
            usage_by_period = forecaster.get_usage_by_period(days, period)

            if usage_by_period:
                st.bar_chart(usage_by_period)
            else:
                st.info("No usage data yet.")

        st.divider()

        st.subheader("Usage by Product")

        usage_by_product = forecaster.get_usage_by_product(days)

        if usage_by_product:
            table_data = []
            for item in usage_by_product[:20]:  # Top 20
                mesh_config = manager.get_mesh_types().get(item["mesh_type"], {})
                table_data.append({
                    "Mesh Type": mesh_config.get("name", item["mesh_type"]),
                    "Width": f"{item['width_mm']}mm",
                    "Colour": item["colour"],
                    "Rolls Used": item["rolls_used"],
                    "Metres Used": f"{item['metres_used']:.0f}m",
                    "Avg Daily": f"{item['avg_daily_metres']:.2f}m/day"
                })

            st.dataframe(table_data, use_container_width=True, hide_index=True)
        else:
            st.info("No usage data yet.")

    # -------------------------
    # TAB 4: Reorder Suggestions
    # -------------------------
    with tab4:
        st.subheader("📋 Reorder Suggestions")
        st.info(
            "Suggestions are based on maintaining stock for **lead time + 2 months buffer**. "
            "Mesh lead time is 4 months, so we target 6 months of stock."
        )

        suggestions = forecaster.get_reorder_suggestions()

        if suggestions:
            for s in suggestions:
                urgency_color = {
                    "CRITICAL": "🔴",
                    "ORDER_NOW": "🟠",
                    "LOW": "🟡"
                }.get(s["urgency"], "")

                with st.expander(
                    f"{urgency_color} {s['mesh_name']} - {s['width_mm']}mm - {s['colour']}",
                    expanded=s["urgency"] == "CRITICAL"
                ):
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.metric("Current Stock", f"{s['current_metres']:.0f}m")

                    with col2:
                        st.metric("Suggested Order", f"{s['suggested_order_metres']:.0f}m")

                    with col3:
                        st.metric("Urgency", s["urgency"])

                    st.caption(s["reason"])
        else:
            st.success("✅ All items have sufficient stock!")

    # -------------------------
    # TAB 5: Shopify Usage Summary
    # -------------------------
    with tab5:
        st.subheader("📊 Shopify Usage Summary")
        st.caption("Component usage calculated from shipped orders")

        usage = forecaster.get_shopify_usage()

        if usage.get("order_count", 0) > 0:
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Orders Analyzed", f"{usage.get('order_count', 0):,}")
                st.metric("Period", f"{usage.get('period_days', 0)} days")

            with col2:
                st.metric("Total Saddles", f"{usage.get('saddles', 0):,}")
                st.metric("Total Trims", f"{usage.get('trims', 0):,}")

            with col3:
                st.metric("Saddle Screws", f"{usage.get('saddle_screws', 0):,}")
                st.metric("Trim Screws", f"{usage.get('trim_screws', 0):,}")

            st.divider()

            st.markdown("### Daily Averages")

            daily_avg = usage.get("daily_avg", {})

            if daily_avg:
                col1, col2, col3, col4, col5 = st.columns(5)

                with col1:
                    st.metric("Saddles/day", f"{daily_avg.get('saddles', 0):.1f}")

                with col2:
                    st.metric("Saddle Screws/day", f"{daily_avg.get('saddle_screws', 0):.1f}")

                with col3:
                    st.metric("Trim Screws/day", f"{daily_avg.get('trim_screws', 0):.1f}")

                with col4:
                    st.metric("Mesh Screws/day", f"{daily_avg.get('mesh_screws', 0):.1f}")

                with col5:
                    st.metric("Trims/day", f"{daily_avg.get('trims', 0):.1f}")

            st.divider()

            # Force refresh button
            if st.button("🔄 Refresh Shopify Data"):
                try:
                    from core.shopify_sync import ShopifySync
                    sync = ShopifySync()
                    new_usage = sync.calculate_component_usage(days=180)
                    st.success(f"Refreshed! Analyzed {new_usage.get('order_count', 0):,} orders.")
                    st.cache_resource.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.warning(
                "No Shopify order data available.\n\n"
                "Possible reasons:\n"
                "- No shipped orders in the last 180 days\n"
                "- API connection issue\n"
                "- Kit breakdown file not found"
            )


def _get_status_emoji(status: str) -> str:
    """Get emoji for status."""
    return {
        "OK": "✅",
        "LOW": "🟡",
        "ORDER_NOW": "🟠",
        "CRITICAL": "🔴",
        "NO_USAGE": "⚪",
        "COIL": "🔵"
    }.get(status, "")


if __name__ == "__main__":
    main()
