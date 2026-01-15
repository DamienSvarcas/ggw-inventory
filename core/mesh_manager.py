"""
Mesh Roll Inventory Manager

Tracks mesh roll inventory by type, width, length, and colour.
Provides forecasting based on usage history.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional
import uuid

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "mesh_config.json")
DATA_PATH = os.path.join(BASE_DIR, "data", "mesh_rolls.json")


class MeshManager:
    """Manages mesh roll inventory and usage tracking."""

    def __init__(self):
        self.config = self._load_config()
        self.data = self._load_data()

    def _load_config(self) -> dict:
        """Load mesh configuration."""
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)

    def _load_data(self) -> dict:
        """Load mesh inventory data."""
        with open(DATA_PATH, "r") as f:
            return json.load(f)

    def _save_data(self):
        """Save mesh inventory data."""
        self.data["last_updated"] = datetime.utcnow().isoformat() + "Z"
        with open(DATA_PATH, "w") as f:
            json.dump(self.data, f, indent=2)

    # -------------------------
    # Inventory Management
    # -------------------------

    def add_roll(
        self,
        mesh_type: str,
        width_mm: int,
        length_m: int,
        colour: str,
        quantity: int = 1,
        received_date: Optional[str] = None,
        location: str = "Warehouse",
        notes: str = ""
    ) -> dict:
        """
        Add mesh roll(s) to inventory.

        Args:
            mesh_type: '4mm_aluminium' or '2mm_ember_guard'
            width_mm: Width in mm (250, 500, 750, 1000)
            length_m: Length in metres (10, 20, 30)
            colour: Colorbond colour name
            quantity: Number of rolls to add
            received_date: Date received (YYYY-MM-DD), defaults to today
            location: Storage location
            notes: Optional notes

        Returns:
            The created inventory entry
        """
        if received_date is None:
            received_date = datetime.now().strftime("%Y-%m-%d")

        entry = {
            "id": str(uuid.uuid4())[:8],
            "mesh_type": mesh_type,
            "width_mm": width_mm,
            "length_m": length_m,
            "colour": colour,
            "quantity": quantity,
            "received_date": received_date,
            "location": location,
            "notes": notes,
            "created_at": datetime.utcnow().isoformat() + "Z"
        }

        self.data["inventory"].append(entry)
        self._save_data()
        return entry

    def remove_roll(
        self,
        mesh_type: str,
        width_mm: int,
        length_m: int,
        colour: str,
        quantity: int = 1,
        reason: str = "order",
        order_id: Optional[str] = None
    ) -> bool:
        """
        Remove mesh roll(s) from inventory (used/sold).

        Args:
            mesh_type: '4mm_aluminium' or '2mm_ember_guard'
            width_mm: Width in mm
            length_m: Length in metres
            colour: Colorbond colour name
            quantity: Number of rolls to remove
            reason: 'order', 'damaged', 'adjustment'
            order_id: Shopify order ID if applicable

        Returns:
            True if successful, False if insufficient stock
        """
        # Find matching inventory entries
        remaining = quantity
        for entry in self.data["inventory"]:
            if (entry["mesh_type"] == mesh_type and
                entry["width_mm"] == width_mm and
                entry["length_m"] == length_m and
                entry["colour"] == colour and
                entry["quantity"] > 0):

                deduct = min(entry["quantity"], remaining)
                entry["quantity"] -= deduct
                remaining -= deduct

                # Log usage
                usage = {
                    "date": datetime.utcnow().isoformat() + "Z",
                    "mesh_type": mesh_type,
                    "width_mm": width_mm,
                    "length_m": length_m,
                    "colour": colour,
                    "quantity": deduct,
                    "reason": reason,
                    "order_id": order_id
                }
                self.data["usage_history"].append(usage)

                if remaining == 0:
                    break

        if remaining > 0:
            return False  # Insufficient stock

        # Remove zero-quantity entries
        self.data["inventory"] = [
            e for e in self.data["inventory"] if e["quantity"] > 0
        ]

        self._save_data()
        return True

    def get_stock_level(
        self,
        mesh_type: Optional[str] = None,
        width_mm: Optional[int] = None,
        length_m: Optional[int] = None,
        colour: Optional[str] = None
    ) -> int:
        """
        Get current stock level (number of rolls).

        Filter by any combination of mesh_type, width, length, colour.
        Returns total quantity matching the filters.
        """
        total = 0
        for entry in self.data["inventory"]:
            if mesh_type and entry["mesh_type"] != mesh_type:
                continue
            if width_mm and entry["width_mm"] != width_mm:
                continue
            if length_m and entry["length_m"] != length_m:
                continue
            if colour and entry["colour"] != colour:
                continue
            total += entry["quantity"]
        return total

    def get_stock_metres(
        self,
        mesh_type: Optional[str] = None,
        width_mm: Optional[int] = None,
        colour: Optional[str] = None
    ) -> float:
        """
        Get current stock in total metres.

        Sums up (quantity * length_m) for all matching rolls.
        """
        total_metres = 0.0
        for entry in self.data["inventory"]:
            if mesh_type and entry["mesh_type"] != mesh_type:
                continue
            if width_mm and entry["width_mm"] != width_mm:
                continue
            if colour and entry["colour"] != colour:
                continue
            total_metres += entry["quantity"] * entry["length_m"]
        return total_metres

    def get_inventory_summary(self) -> list:
        """
        Get summarized inventory by mesh_type, width, length, colour.

        Returns list of dicts with aggregated quantities.
        """
        summary = {}
        for entry in self.data["inventory"]:
            key = (
                entry["mesh_type"],
                entry["width_mm"],
                entry["length_m"],
                entry["colour"]
            )
            if key not in summary:
                summary[key] = {
                    "mesh_type": entry["mesh_type"],
                    "width_mm": entry["width_mm"],
                    "length_m": entry["length_m"],
                    "colour": entry["colour"],
                    "quantity": 0,
                    "total_metres": 0
                }
            summary[key]["quantity"] += entry["quantity"]
            summary[key]["total_metres"] += entry["quantity"] * entry["length_m"]

        return list(summary.values())

    # -------------------------
    # Usage Analysis
    # -------------------------

    def get_usage(self, days: int = 180) -> list:
        """
        Get usage history for the last N days.

        Default is 180 days (6 months) for forecasting.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        usage = []
        for u in self.data["usage_history"]:
            usage_date = datetime.fromisoformat(u["date"].replace("Z", "+00:00"))
            if usage_date >= cutoff:
                usage.append(u)
        return usage

    def get_average_daily_usage(
        self,
        mesh_type: Optional[str] = None,
        width_mm: Optional[int] = None,
        colour: Optional[str] = None,
        days: int = 180
    ) -> float:
        """
        Calculate average daily usage in metres.

        Based on usage history over the specified period.
        """
        usage = self.get_usage(days)
        total_metres = 0.0

        for u in usage:
            if mesh_type and u["mesh_type"] != mesh_type:
                continue
            if width_mm and u["width_mm"] != width_mm:
                continue
            if colour and u["colour"] != colour:
                continue
            total_metres += u["quantity"] * u["length_m"]

        return total_metres / days if days > 0 else 0.0

    # -------------------------
    # Forecasting
    # -------------------------

    def get_days_remaining(
        self,
        mesh_type: Optional[str] = None,
        width_mm: Optional[int] = None,
        colour: Optional[str] = None
    ) -> float:
        """
        Calculate estimated days of stock remaining.

        Based on current stock and average daily usage.
        Returns float('inf') if no usage history.
        """
        current_metres = self.get_stock_metres(mesh_type, width_mm, colour)
        daily_usage = self.get_average_daily_usage(mesh_type, width_mm, colour)

        if daily_usage == 0:
            return float("inf")

        return current_metres / daily_usage

    def get_months_remaining(
        self,
        mesh_type: Optional[str] = None,
        width_mm: Optional[int] = None,
        colour: Optional[str] = None
    ) -> float:
        """Calculate estimated months of stock remaining."""
        days = self.get_days_remaining(mesh_type, width_mm, colour)
        if days == float("inf"):
            return float("inf")
        return days / 30.0

    def get_reorder_alerts(self) -> list:
        """
        Get list of mesh items that need reordering.

        Based on thresholds in config (default: alert when < 5 months stock).
        """
        alerts = []
        threshold = self.config["reorder_thresholds"]["alert_months_stock"]

        # Group by mesh_type, width, colour
        groups = {}
        for entry in self.data["inventory"]:
            key = (entry["mesh_type"], entry["width_mm"], entry["colour"])
            if key not in groups:
                groups[key] = 0
            groups[key] += entry["quantity"] * entry["length_m"]

        for (mesh_type, width, colour), metres in groups.items():
            months = self.get_months_remaining(mesh_type, width, colour)
            if months < threshold and months != float("inf"):
                mesh_config = self.config["mesh_types"].get(mesh_type, {})
                alerts.append({
                    "mesh_type": mesh_type,
                    "mesh_name": mesh_config.get("name", mesh_type),
                    "width_mm": width,
                    "colour": colour,
                    "current_metres": metres,
                    "months_remaining": round(months, 1),
                    "lead_time_months": mesh_config.get("lead_time_months", 4),
                    "urgency": "HIGH" if months < 4 else "MEDIUM"
                })

        return sorted(alerts, key=lambda x: x["months_remaining"])

    # -------------------------
    # Mesh Cutting
    # -------------------------

    def get_cutting_options(self, source_width_mm: int) -> list:
        """
        Get valid cutting options for a source width.

        Returns list of cutting presets.
        """
        options = []

        if source_width_mm == 1000:
            options = [
                {"label": "4x 250mm", "widths": [250, 250, 250, 250]},
                {"label": "2x 500mm", "widths": [500, 500]},
                {"label": "1x 500mm + 2x 250mm", "widths": [500, 250, 250]},
                {"label": "1x 750mm + 1x 250mm", "widths": [750, 250]},
            ]
        elif source_width_mm == 500:
            options = [
                {"label": "2x 250mm", "widths": [250, 250]},
            ]
        elif source_width_mm == 750:
            options = [
                {"label": "3x 250mm", "widths": [250, 250, 250]},
                {"label": "1x 500mm + 1x 250mm", "widths": [500, 250]},
            ]

        return options

    def cut_roll(
        self,
        mesh_type: str,
        source_width_mm: int,
        length_m: int,
        colour: str,
        target_widths: list,
        operator: str = "",
        notes: str = ""
    ) -> dict:
        """
        Cut a wide roll into smaller widths.

        Example: Cut 1x 1000mm roll into 4x 250mm rolls.
        - Removes 1x source roll from inventory
        - Adds resulting rolls (same length, mesh_type, colour)
        - Logs the cutting operation

        Args:
            mesh_type: '4mm_aluminium' or '2mm_ember_guard'
            source_width_mm: Width of source roll (1000, 750, 500)
            length_m: Length of the roll being cut
            colour: Colorbond colour
            target_widths: List of target widths e.g. [250, 250, 250, 250]
            operator: Name of person doing the cut
            notes: Optional notes

        Returns:
            Dict with cut details and result rolls

        Raises:
            ValueError: If source roll not in stock or invalid cut
        """
        # Validate total width matches
        total_target = sum(target_widths)
        if total_target != source_width_mm:
            raise ValueError(
                f"Target widths ({total_target}mm) must equal source width ({source_width_mm}mm)"
            )

        # Check source roll exists
        source_stock = self.get_stock_level(mesh_type, source_width_mm, length_m, colour)
        if source_stock < 1:
            raise ValueError(
                f"No {source_width_mm}mm x {length_m}m {colour} roll in stock"
            )

        # Remove source roll
        success = self.remove_roll(
            mesh_type=mesh_type,
            width_mm=source_width_mm,
            length_m=length_m,
            colour=colour,
            quantity=1,
            reason="cut",
            order_id=None
        )

        if not success:
            raise ValueError("Failed to remove source roll")

        # Add result rolls
        result_rolls = []
        width_counts = {}
        for w in target_widths:
            width_counts[w] = width_counts.get(w, 0) + 1

        for width, qty in width_counts.items():
            entry = self.add_roll(
                mesh_type=mesh_type,
                width_mm=width,
                length_m=length_m,
                colour=colour,
                quantity=qty,
                notes=f"Cut from {source_width_mm}mm roll"
            )
            result_rolls.append({"width_mm": width, "quantity": qty, "id": entry["id"]})

        # Log cutting operation
        if "cutting_history" not in self.data:
            self.data["cutting_history"] = []

        cut_record = {
            "id": str(uuid.uuid4())[:8],
            "date": datetime.utcnow().isoformat() + "Z",
            "mesh_type": mesh_type,
            "source": {
                "width_mm": source_width_mm,
                "length_m": length_m,
                "colour": colour
            },
            "result": result_rolls,
            "operator": operator,
            "notes": notes
        }

        self.data["cutting_history"].append(cut_record)
        self._save_data()

        return cut_record

    def get_cutting_history(self, days: int = 90) -> list:
        """Get cutting history for the last N days."""
        if "cutting_history" not in self.data:
            return []

        cutoff = datetime.utcnow() - timedelta(days=days)
        history = []

        for record in self.data["cutting_history"]:
            cut_date = datetime.fromisoformat(record["date"].replace("Z", "+00:00"))
            if cut_date >= cutoff:
                history.append(record)

        return sorted(history, key=lambda x: x["date"], reverse=True)

    # -------------------------
    # Incoming Orders (Stock on the Way)
    # -------------------------

    def add_incoming_order(
        self,
        mesh_type: str,
        width_mm: int,
        length_m: int,
        colour: str,
        quantity: int,
        order_date: str,
        expected_delivery: str
    ) -> dict:
        """
        Add an incoming order (stock on the way).

        Args:
            mesh_type: '4mm_aluminium' or '2mm_ember_guard'
            width_mm: Width in mm
            length_m: Length in metres
            colour: Colorbond colour name
            quantity: Number of rolls ordered
            order_date: Date order was placed (YYYY-MM-DD)
            expected_delivery: Expected delivery date (YYYY-MM-DD)

        Returns:
            The created incoming order entry
        """
        if "incoming_orders" not in self.data:
            self.data["incoming_orders"] = []

        entry = {
            "id": str(uuid.uuid4())[:8],
            "mesh_type": mesh_type,
            "width_mm": width_mm,
            "length_m": length_m,
            "colour": colour,
            "quantity": quantity,
            "order_date": order_date,
            "expected_delivery": expected_delivery,
            "status": "ordered",
            "created_at": datetime.utcnow().isoformat() + "Z"
        }

        self.data["incoming_orders"].append(entry)
        self._save_data()
        return entry

    def get_incoming_orders(
        self,
        mesh_type: Optional[str] = None,
        colour: Optional[str] = None,
        status: str = "ordered"
    ) -> list:
        """
        Get incoming orders filtered by criteria.

        Args:
            mesh_type: Filter by mesh type
            colour: Filter by colour
            status: Filter by status ('ordered' or 'received')

        Returns:
            List of matching incoming orders
        """
        if "incoming_orders" not in self.data:
            return []

        orders = []
        for order in self.data["incoming_orders"]:
            if status and order.get("status") != status:
                continue
            if mesh_type and order["mesh_type"] != mesh_type:
                continue
            if colour and order["colour"] != colour:
                continue
            orders.append(order)

        return sorted(orders, key=lambda x: x["expected_delivery"])

    def mark_order_received(self, order_id: str) -> bool:
        """
        Mark an incoming order as received and add to inventory.

        Args:
            order_id: ID of the incoming order

        Returns:
            True if successful, False if order not found
        """
        if "incoming_orders" not in self.data:
            return False

        for order in self.data["incoming_orders"]:
            if order["id"] == order_id and order.get("status") == "ordered":
                # Add to inventory
                self.add_roll(
                    mesh_type=order["mesh_type"],
                    width_mm=order["width_mm"],
                    length_m=order["length_m"],
                    colour=order["colour"],
                    quantity=order["quantity"],
                    received_date=datetime.now().strftime("%Y-%m-%d"),
                    notes=f"Received from incoming order {order_id}"
                )

                # Update order status
                order["status"] = "received"
                order["received_date"] = datetime.now().strftime("%Y-%m-%d")
                self._save_data()
                return True

        return False

    def cancel_incoming_order(self, order_id: str) -> bool:
        """
        Cancel/remove an incoming order.

        Args:
            order_id: ID of the incoming order

        Returns:
            True if successful, False if order not found
        """
        if "incoming_orders" not in self.data:
            return False

        for i, order in enumerate(self.data["incoming_orders"]):
            if order["id"] == order_id and order.get("status") == "ordered":
                del self.data["incoming_orders"][i]
                self._save_data()
                return True

        return False

    def get_incoming_stock(
        self,
        mesh_type: Optional[str] = None,
        width_mm: Optional[int] = None,
        length_m: Optional[int] = None,
        colour: Optional[str] = None
    ) -> int:
        """
        Get total incoming stock (rolls on the way).

        Filter by any combination of mesh_type, width, length, colour.
        Returns total quantity of incoming rolls matching the filters.
        """
        if "incoming_orders" not in self.data:
            return 0

        total = 0
        for order in self.data["incoming_orders"]:
            if order.get("status") != "ordered":
                continue
            if mesh_type and order["mesh_type"] != mesh_type:
                continue
            if width_mm and order["width_mm"] != width_mm:
                continue
            if length_m and order["length_m"] != length_m:
                continue
            if colour and order["colour"] != colour:
                continue
            total += order["quantity"]
        return total

    def get_incoming_metres(
        self,
        mesh_type: Optional[str] = None,
        width_mm: Optional[int] = None,
        colour: Optional[str] = None
    ) -> float:
        """
        Get incoming stock in total metres.

        Sums up (quantity * length_m) for all matching incoming orders.
        """
        if "incoming_orders" not in self.data:
            return 0.0

        total_metres = 0.0
        for order in self.data["incoming_orders"]:
            if order.get("status") != "ordered":
                continue
            if mesh_type and order["mesh_type"] != mesh_type:
                continue
            if width_mm and order["width_mm"] != width_mm:
                continue
            if colour and order["colour"] != colour:
                continue
            total_metres += order["quantity"] * order["length_m"]
        return total_metres

    def get_stock_with_incoming(
        self,
        mesh_type: str,
        width_mm: int,
        length_m: int,
        colour: str
    ) -> dict:
        """
        Get combined stock position including incoming orders.

        Args:
            mesh_type: Mesh type
            width_mm: Width in mm
            length_m: Length in metres
            colour: Colour name

        Returns:
            Dict with on_shelf, incoming, total quantities and metres
        """
        on_shelf_qty = self.get_stock_level(mesh_type, width_mm, length_m, colour)
        incoming_qty = self.get_incoming_stock(mesh_type, width_mm, length_m, colour)

        on_shelf_metres = on_shelf_qty * length_m
        incoming_metres = incoming_qty * length_m

        return {
            "on_shelf_qty": on_shelf_qty,
            "on_shelf_metres": on_shelf_metres,
            "incoming_qty": incoming_qty,
            "incoming_metres": incoming_metres,
            "total_qty": on_shelf_qty + incoming_qty,
            "total_metres": on_shelf_metres + incoming_metres
        }

    def get_incoming_summary(self) -> list:
        """
        Get summarized incoming orders by mesh_type, width, length, colour.

        Returns list of dicts with aggregated quantities.
        """
        if "incoming_orders" not in self.data:
            return []

        summary = {}
        for order in self.data["incoming_orders"]:
            if order.get("status") != "ordered":
                continue
            key = (
                order["mesh_type"],
                order["width_mm"],
                order["length_m"],
                order["colour"]
            )
            if key not in summary:
                summary[key] = {
                    "mesh_type": order["mesh_type"],
                    "width_mm": order["width_mm"],
                    "length_m": order["length_m"],
                    "colour": order["colour"],
                    "quantity": 0,
                    "total_metres": 0
                }
            summary[key]["quantity"] += order["quantity"]
            summary[key]["total_metres"] += order["quantity"] * order["length_m"]

        return list(summary.values())

    # -------------------------
    # Utility
    # -------------------------

    def get_colours(self) -> list:
        """Get list of available colours from config."""
        return self.config["colours"]

    def get_mesh_types(self) -> dict:
        """Get mesh type configurations."""
        return self.config["mesh_types"]


# Command-line interface for testing
if __name__ == "__main__":
    manager = MeshManager()

    print("Mesh Manager CLI")
    print("=" * 40)
    print(f"Config loaded: {len(manager.get_colours())} colours")
    print(f"Current inventory entries: {len(manager.data['inventory'])}")
    print(f"Usage history entries: {len(manager.data['usage_history'])}")
    print()

    # Show summary
    summary = manager.get_inventory_summary()
    if summary:
        print("Current Stock Summary:")
        for item in summary:
            print(f"  {item['mesh_type']} {item['width_mm']}mm - {item['colour']}: "
                  f"{item['quantity']} rolls ({item['total_metres']}m)")
    else:
        print("No inventory yet. Use add_roll() to add stock.")
