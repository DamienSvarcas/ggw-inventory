"""
Inventory Forecasting Module

Provides usage analysis and stock predictions based on Shopify order data.
Supports all inventory types: mesh, saddles, screws, trims, boxes.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MESH_DATA_PATH = os.path.join(BASE_DIR, "data", "mesh_rolls.json")
MESH_CONFIG_PATH = os.path.join(BASE_DIR, "config", "mesh_config.json")
SADDLE_DATA_PATH = os.path.join(BASE_DIR, "data", "saddle_stock.json")
COIL_DATA_PATH = os.path.join(BASE_DIR, "data", "coil_inventory.json")
SCREW_DATA_PATH = os.path.join(BASE_DIR, "data", "screw_inventory.json")
SCREW_CONFIG_PATH = os.path.join(BASE_DIR, "config", "screw_config.json")
BOX_DATA_PATH = os.path.join(BASE_DIR, "data", "box_inventory.json")
BOX_CONFIG_PATH = os.path.join(BASE_DIR, "config", "box_config.json")


class Forecaster:
    """Provides forecasting and usage analysis for all inventory types."""

    def __init__(self):
        self.mesh_config = self._load_json(MESH_CONFIG_PATH)
        self.mesh_data = self._load_json(MESH_DATA_PATH)
        self.saddle_data = self._load_json(SADDLE_DATA_PATH)
        self.coil_data = self._load_json(COIL_DATA_PATH)
        self.screw_data = self._load_json(SCREW_DATA_PATH)
        self.screw_config = self._load_json(SCREW_CONFIG_PATH)
        self.box_data = self._load_json(BOX_DATA_PATH)
        self.box_config = self._load_json(BOX_CONFIG_PATH)
        self._shopify_usage = None

    def _load_json(self, path: str) -> dict:
        """Load JSON file, return empty dict if not found."""
        try:
            with open(path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def reload_data(self):
        """Reload all data from disk."""
        self.mesh_data = self._load_json(MESH_DATA_PATH)
        self.saddle_data = self._load_json(SADDLE_DATA_PATH)
        self.coil_data = self._load_json(COIL_DATA_PATH)
        self.screw_data = self._load_json(SCREW_DATA_PATH)
        self.box_data = self._load_json(BOX_DATA_PATH)
        self._shopify_usage = None

    def get_shopify_usage(self, days: int = 180, force_refresh: bool = False) -> dict:
        """
        Get component usage from Shopify orders.

        Returns dict with usage for each component type.
        """
        if self._shopify_usage and not force_refresh:
            return self._shopify_usage

        try:
            from core.shopify_sync import ShopifySync
            sync = ShopifySync()
            self._shopify_usage = sync.calculate_component_usage(days=days)
            return self._shopify_usage
        except Exception as e:
            print(f"Shopify sync error: {e}")
            return {
                "mesh": [],
                "saddles": 0,
                "saddle_screws": 0,
                "trim_screws": 0,
                "mesh_screws": 0,
                "trims": 0,
                "order_count": 0,
                "period_days": days,
                "daily_avg": {
                    "saddles": 0,
                    "saddle_screws": 0,
                    "trim_screws": 0,
                    "mesh_screws": 0,
                    "trims": 0
                }
            }

    # -------------------------
    # Mesh Usage Analysis (from local history)
    # -------------------------

    def get_usage_by_period(
        self,
        days: int = 180,
        group_by: str = "week"
    ) -> dict:
        """
        Get usage grouped by time period.

        Args:
            days: Number of days to analyze
            group_by: 'day', 'week', or 'month'

        Returns:
            Dict with period keys and usage in metres
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        usage_by_period = defaultdict(float)

        for u in self.mesh_data.get("usage_history", []):
            usage_date = datetime.fromisoformat(u["date"].replace("Z", "+00:00"))
            if usage_date < cutoff:
                continue

            metres = u["quantity"] * u["length_m"]

            if group_by == "day":
                key = usage_date.strftime("%Y-%m-%d")
            elif group_by == "week":
                key = usage_date.strftime("%Y-W%W")
            elif group_by == "month":
                key = usage_date.strftime("%Y-%m")
            else:
                key = usage_date.strftime("%Y-%m-%d")

            usage_by_period[key] += metres

        return dict(sorted(usage_by_period.items()))

    def get_usage_by_product(
        self,
        days: int = 180
    ) -> list:
        """
        Get usage grouped by product (mesh_type + width + colour).

        Returns list sorted by total metres used (descending).
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        usage_by_product = defaultdict(lambda: {"quantity": 0, "metres": 0})

        for u in self.mesh_data.get("usage_history", []):
            usage_date = datetime.fromisoformat(u["date"].replace("Z", "+00:00"))
            if usage_date < cutoff:
                continue

            key = (u["mesh_type"], u["width_mm"], u["colour"])
            usage_by_product[key]["quantity"] += u["quantity"]
            usage_by_product[key]["metres"] += u["quantity"] * u["length_m"]

        result = []
        for (mesh_type, width, colour), data in usage_by_product.items():
            result.append({
                "mesh_type": mesh_type,
                "width_mm": width,
                "colour": colour,
                "rolls_used": data["quantity"],
                "metres_used": data["metres"],
                "avg_daily_metres": round(data["metres"] / days, 2)
            })

        return sorted(result, key=lambda x: x["metres_used"], reverse=True)

    # -------------------------
    # Mesh Forecasting
    # -------------------------

    def calculate_stock_forecast(self) -> list:
        """
        Calculate stock forecast for all mesh products.

        Returns list with current stock, usage rate, and predictions.
        """
        # Get current inventory
        inventory_by_product = defaultdict(float)
        for entry in self.mesh_data.get("inventory", []):
            key = (entry["mesh_type"], entry["width_mm"], entry["colour"])
            inventory_by_product[key] += entry["quantity"] * entry["length_m"]

        # Get usage (last 180 days)
        usage_by_product = {}
        for item in self.get_usage_by_product(180):
            key = (item["mesh_type"], item["width_mm"], item["colour"])
            usage_by_product[key] = item["avg_daily_metres"]

        # Build forecast
        forecasts = []
        mesh_types = self.mesh_config.get("mesh_types", {})

        all_keys = set(inventory_by_product.keys()) | set(usage_by_product.keys())

        for key in all_keys:
            mesh_type, width, colour = key
            current_metres = inventory_by_product.get(key, 0)
            daily_usage = usage_by_product.get(key, 0)

            if daily_usage > 0:
                days_remaining = current_metres / daily_usage
                months_remaining = days_remaining / 30
            else:
                days_remaining = float("inf")
                months_remaining = float("inf")

            mesh_config = mesh_types.get(mesh_type, {})
            lead_time = mesh_config.get("lead_time_months", 4)

            # Determine status
            if months_remaining == float("inf"):
                status = "NO_USAGE"
            elif months_remaining < lead_time:
                status = "CRITICAL"
            elif months_remaining < lead_time + 1:
                status = "ORDER_NOW"
            elif months_remaining < lead_time + 2:
                status = "LOW"
            else:
                status = "OK"

            forecasts.append({
                "mesh_type": mesh_type,
                "mesh_name": mesh_config.get("name", mesh_type),
                "width_mm": width,
                "colour": colour,
                "current_metres": round(current_metres, 1),
                "avg_daily_usage": round(daily_usage, 2),
                "avg_monthly_usage": round(daily_usage * 30, 1),
                "days_remaining": round(days_remaining, 0) if days_remaining != float("inf") else None,
                "months_remaining": round(months_remaining, 1) if months_remaining != float("inf") else None,
                "lead_time_months": lead_time,
                "status": status
            })

        return sorted(forecasts, key=lambda x: (
            x["status"] == "OK",
            x["status"] == "NO_USAGE",
            x["days_remaining"] or float("inf")
        ))

    def get_reorder_suggestions(self) -> list:
        """
        Get suggested reorder quantities based on lead time and usage.

        Suggests ordering enough stock for lead_time + 2 months buffer.
        """
        forecasts = self.calculate_stock_forecast()
        suggestions = []

        for f in forecasts:
            if f["status"] in ["CRITICAL", "ORDER_NOW", "LOW"]:
                # Calculate how much to order
                lead_time = f["lead_time_months"]
                buffer_months = 2
                target_months = lead_time + buffer_months

                monthly_usage = f["avg_monthly_usage"]
                current_metres = f["current_metres"]

                if monthly_usage > 0:
                    target_metres = monthly_usage * target_months
                    order_metres = max(0, target_metres - current_metres)

                    suggestions.append({
                        "mesh_type": f["mesh_type"],
                        "mesh_name": f["mesh_name"],
                        "width_mm": f["width_mm"],
                        "colour": f["colour"],
                        "current_metres": f["current_metres"],
                        "suggested_order_metres": round(order_metres, 0),
                        "reason": f"Stock below {target_months} months ({f['status']})",
                        "urgency": f["status"]
                    })

        return suggestions

    # -------------------------
    # Component Forecasting (Shopify-based)
    # -------------------------

    def get_component_forecast(self, days: int = 180) -> dict:
        """
        Get forecast for all components based on Shopify usage.

        Returns dict with forecasts for saddles, screws, trims, boxes.
        """
        usage = self.get_shopify_usage(days)
        daily_avg = usage.get("daily_avg", {})

        forecasts = {
            "saddles": self._forecast_saddles(daily_avg.get("saddles", 0)),
            "screws": self._forecast_screws(daily_avg),
            "trims": self._forecast_trims(daily_avg.get("trims", 0)),
            "boxes": self._forecast_boxes(daily_avg),
            "usage_summary": {
                "period_days": usage.get("period_days", days),
                "order_count": usage.get("order_count", 0),
                "total_saddles": usage.get("saddles", 0),
                "total_saddle_screws": usage.get("saddle_screws", 0),
                "total_trim_screws": usage.get("trim_screws", 0),
                "total_trims": usage.get("trims", 0)
            }
        }

        return forecasts

    def _forecast_saddles(self, daily_usage: float) -> list:
        """Forecast saddle stock levels."""
        forecasts = []

        # Get current saddle stock
        for entry in self.saddle_data.get("inventory", []):
            if entry.get("quantity", 0) <= 0:
                continue

            current_qty = entry["quantity"]
            saddle_type = entry.get("saddle_type", "corrugated")
            colour = entry.get("colour", "Unknown")

            # Simple forecast based on overall daily usage
            # (In production, would break down by type/colour)
            if daily_usage > 0:
                days_remaining = current_qty / daily_usage
            else:
                days_remaining = float("inf")

            status = self._get_status(days_remaining, lead_time_days=14)

            forecasts.append({
                "type": "saddle",
                "saddle_type": saddle_type,
                "colour": colour,
                "current_qty": current_qty,
                "daily_usage": round(daily_usage, 1),
                "days_remaining": round(days_remaining, 0) if days_remaining != float("inf") else None,
                "status": status
            })

        # Also add forecast from coils (estimated yield)
        for coil in self.coil_data.get("inventory", []):
            if coil.get("status") != "in_use" and coil.get("current_weight_kg", 0) > 0:
                continue
            if coil.get("saddle_type") == "trim":
                continue

            weight_kg = coil.get("current_weight_kg", 0)
            yield_per_kg = 66  # saddles per kg
            waste = 0.27
            estimated_saddles = int(weight_kg * (1 - waste) * yield_per_kg)

            if estimated_saddles > 0:
                if daily_usage > 0:
                    days_remaining = estimated_saddles / daily_usage
                else:
                    days_remaining = float("inf")

                forecasts.append({
                    "type": "coil_yield",
                    "saddle_type": coil.get("saddle_type", "corrugated"),
                    "colour": coil.get("colour", "Unknown"),
                    "current_qty": estimated_saddles,
                    "coil_weight_kg": weight_kg,
                    "daily_usage": round(daily_usage, 1),
                    "days_remaining": round(days_remaining, 0) if days_remaining != float("inf") else None,
                    "status": "COIL"
                })

        return forecasts

    def _forecast_screws(self, daily_avg: dict) -> list:
        """Forecast screw stock levels."""
        forecasts = []

        screw_types = self.screw_config.get("screw_types", {})

        for entry in self.screw_data.get("inventory", []):
            if entry.get("quantity", 0) <= 0:
                continue

            screw_type = entry.get("screw_type", "")
            current_qty = entry["quantity"]
            colour = entry.get("colour", "")

            # Map screw type to usage key
            usage_key_map = {
                "saddle_screw": "saddle_screws",
                "trim_screw": "trim_screws",
                "mesh_screw": "mesh_screws"
            }
            usage_key = usage_key_map.get(screw_type, "saddle_screws")
            daily_usage = daily_avg.get(usage_key, 0)

            if daily_usage > 0:
                days_remaining = current_qty / daily_usage
            else:
                days_remaining = float("inf")

            status = self._get_status(days_remaining, lead_time_days=7)

            type_config = screw_types.get(screw_type, {})
            forecasts.append({
                "screw_type": screw_type,
                "screw_name": type_config.get("name", screw_type),
                "colour": colour,
                "current_qty": current_qty,
                "daily_usage": round(daily_usage, 1),
                "days_remaining": round(days_remaining, 0) if days_remaining != float("inf") else None,
                "status": status
            })

        return forecasts

    def _forecast_trims(self, daily_usage: float) -> list:
        """Forecast trim stock levels."""
        forecasts = []

        # Get trim stock from saddle_stock.json (trims stored with saddles)
        for entry in self.saddle_data.get("inventory", []):
            if entry.get("saddle_type") != "trim":
                continue
            if entry.get("quantity", 0) <= 0:
                continue

            current_qty = entry["quantity"]
            colour = entry.get("colour", "Unknown")

            if daily_usage > 0:
                days_remaining = current_qty / daily_usage
            else:
                days_remaining = float("inf")

            status = self._get_status(days_remaining, lead_time_days=14)

            forecasts.append({
                "type": "trim",
                "colour": colour,
                "current_qty": current_qty,
                "daily_usage": round(daily_usage, 1),
                "days_remaining": round(days_remaining, 0) if days_remaining != float("inf") else None,
                "status": status
            })

        # Also add forecast from trim coils (estimated yield)
        for coil in self.coil_data.get("inventory", []):
            if coil.get("saddle_type") != "trim":
                continue
            if coil.get("current_weight_kg", 0) <= 0:
                continue

            weight_kg = coil.get("current_weight_kg", 0)
            yield_per_kg = 8.4  # trims per kg
            estimated_trims = int(weight_kg * yield_per_kg)

            if estimated_trims > 0:
                if daily_usage > 0:
                    days_remaining = estimated_trims / daily_usage
                else:
                    days_remaining = float("inf")

                forecasts.append({
                    "type": "coil_yield",
                    "colour": coil.get("colour", "Unknown"),
                    "current_qty": estimated_trims,
                    "coil_weight_kg": weight_kg,
                    "daily_usage": round(daily_usage, 1),
                    "days_remaining": round(days_remaining, 0) if days_remaining != float("inf") else None,
                    "status": "COIL"
                })

        return forecasts

    def _forecast_boxes(self, daily_avg: dict) -> list:
        """Forecast box stock levels."""
        forecasts = []

        box_types = self.box_config.get("box_types", {})

        # Estimate daily box usage based on order count
        # Assume ~1 box per order on average
        usage = self.get_shopify_usage()
        order_count = usage.get("order_count", 0)
        period_days = usage.get("period_days", 180)
        daily_orders = order_count / period_days if period_days > 0 else 0

        for entry in self.box_data.get("inventory", []):
            if entry.get("quantity", 0) <= 0:
                continue

            box_type = entry.get("box_type", "")
            current_qty = entry["quantity"]

            # Rough estimate: 50% small tube, 30% large tube, 20% saddle box
            usage_ratios = {
                "small_tube": 0.5,
                "large_tube": 0.3,
                "saddle_box": 0.2
            }
            daily_usage = daily_orders * usage_ratios.get(box_type, 0.33)

            if daily_usage > 0:
                days_remaining = current_qty / daily_usage
            else:
                days_remaining = float("inf")

            status = self._get_status(days_remaining, lead_time_days=7)

            type_config = box_types.get(box_type, {})
            forecasts.append({
                "box_type": box_type,
                "box_name": type_config.get("name", box_type),
                "current_qty": current_qty,
                "daily_usage": round(daily_usage, 1),
                "days_remaining": round(days_remaining, 0) if days_remaining != float("inf") else None,
                "status": status
            })

        return forecasts

    def _get_status(self, days_remaining: float, lead_time_days: int = 14) -> str:
        """Determine status based on days remaining."""
        if days_remaining == float("inf"):
            return "NO_USAGE"
        elif days_remaining < lead_time_days:
            return "CRITICAL"
        elif days_remaining < lead_time_days * 2:
            return "ORDER_NOW"
        elif days_remaining < lead_time_days * 3:
            return "LOW"
        else:
            return "OK"

    # -------------------------
    # Summary Statistics
    # -------------------------

    def get_summary_stats(self) -> dict:
        """
        Get overall inventory summary statistics.
        """
        inventory = self.mesh_data.get("inventory", [])
        usage_history = self.mesh_data.get("usage_history", [])

        # Total stock
        total_rolls = sum(e["quantity"] for e in inventory)
        total_metres = sum(e["quantity"] * e["length_m"] for e in inventory)

        # Unique products
        unique_products = set(
            (e["mesh_type"], e["width_mm"], e["colour"])
            for e in inventory if e["quantity"] > 0
        )

        # Usage last 30 days
        cutoff_30 = datetime.utcnow() - timedelta(days=30)
        usage_30_metres = sum(
            u["quantity"] * u["length_m"]
            for u in usage_history
            if datetime.fromisoformat(u["date"].replace("Z", "+00:00")) >= cutoff_30
        )

        # Items needing reorder
        forecasts = self.calculate_stock_forecast()
        critical_items = [f for f in forecasts if f["status"] in ["CRITICAL", "ORDER_NOW"]]
        low_items = [f for f in forecasts if f["status"] == "LOW"]

        # Component summary
        component_forecast = self.get_component_forecast()

        return {
            "total_rolls": total_rolls,
            "total_metres": round(total_metres, 1),
            "unique_products": len(unique_products),
            "usage_last_30_days_metres": round(usage_30_metres, 1),
            "critical_items": len(critical_items),
            "low_stock_items": len(low_items),
            "last_updated": self.mesh_data.get("last_updated"),
            "shopify_orders_analyzed": component_forecast.get("usage_summary", {}).get("order_count", 0)
        }

    def get_all_forecasts(self) -> dict:
        """
        Get comprehensive forecast for all inventory types.

        Returns dict with mesh, saddle, screw, trim, and box forecasts.
        """
        return {
            "mesh": self.calculate_stock_forecast(),
            "components": self.get_component_forecast(),
            "reorder_suggestions": self.get_reorder_suggestions(),
            "summary": self.get_summary_stats()
        }


# Command-line interface for testing
if __name__ == "__main__":
    forecaster = Forecaster()

    print("Forecaster CLI")
    print("=" * 40)

    stats = forecaster.get_summary_stats()
    print(f"Total Stock: {stats['total_rolls']} rolls ({stats['total_metres']}m)")
    print(f"Unique Products: {stats['unique_products']}")
    print(f"Usage (30 days): {stats['usage_last_30_days_metres']}m")
    print(f"Critical Items: {stats['critical_items']}")
    print(f"Low Stock Items: {stats['low_stock_items']}")
    print(f"Shopify Orders Analyzed: {stats['shopify_orders_analyzed']}")

    print("\nComponent Forecast:")
    print("-" * 40)

    component_forecast = forecaster.get_component_forecast()
    usage = component_forecast.get("usage_summary", {})
    print(f"Orders analyzed: {usage.get('order_count', 0)}")
    print(f"Total saddles used: {usage.get('total_saddles', 0):,}")
    print(f"Total saddle screws: {usage.get('total_saddle_screws', 0):,}")
    print(f"Total trim screws: {usage.get('total_trim_screws', 0):,}")
    print(f"Total trims: {usage.get('total_trims', 0):,}")
