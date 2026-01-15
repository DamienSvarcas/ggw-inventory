"""
Screw Inventory Manager

Tracks screw stock by type (saddle, trim, mesh/tile) AND colour.
Simple add/remove stock management.
"""

import json
import os
from datetime import datetime
from typing import Optional
import uuid

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "screw_config.json")
DATA_PATH = os.path.join(BASE_DIR, "data", "screw_inventory.json")


class ScrewManager:
    """Manages screw inventory by type and colour."""

    def __init__(self):
        self.config = self._load_config()
        self.data = self._load_data()

    def _load_config(self) -> dict:
        """Load screw configuration."""
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)

    def _load_data(self) -> dict:
        """Load screw inventory data."""
        with open(DATA_PATH, "r") as f:
            return json.load(f)

    def _save_data(self):
        """Save screw inventory data."""
        self.data["last_updated"] = datetime.utcnow().isoformat() + "Z"
        with open(DATA_PATH, "w") as f:
            json.dump(self.data, f, indent=2)

    # -------------------------
    # Stock Management
    # -------------------------

    def add_stock(
        self,
        screw_type: str,
        colour: str,
        quantity: int,
        source: str = "received",
        notes: str = ""
    ) -> dict:
        """
        Add screws to inventory.

        Args:
            screw_type: 'saddle', 'trim', 'mesh_tile'
            colour: Colour name (e.g., 'Monument', 'Woodland Grey')
            quantity: Number of screws to add
            source: 'received', 'adjustment', 'return'
            notes: Optional notes

        Returns:
            Updated stock entry
        """
        # Find existing entry or create new
        for entry in self.data["inventory"]:
            if entry["screw_type"] == screw_type and entry["colour"] == colour:
                entry["quantity"] += quantity
                entry["last_updated"] = datetime.utcnow().isoformat() + "Z"
                self._save_data()
                return entry

        # Create new entry
        entry = {
            "id": str(uuid.uuid4())[:8],
            "screw_type": screw_type,
            "colour": colour,
            "quantity": quantity,
            "source": source,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "last_updated": datetime.utcnow().isoformat() + "Z"
        }
        self.data["inventory"].append(entry)
        self._save_data()
        return entry

    def remove_stock(
        self,
        screw_type: str,
        colour: str,
        quantity: int,
        reason: str = "order",
        order_id: Optional[str] = None
    ) -> bool:
        """
        Remove screws from inventory.

        Args:
            screw_type: Type of screw
            colour: Colour of screw
            quantity: Number to remove
            reason: 'order', 'damaged', 'adjustment'
            order_id: Shopify order ID if applicable

        Returns:
            True if successful, False if insufficient stock
        """
        for entry in self.data["inventory"]:
            if entry["screw_type"] == screw_type and entry["colour"] == colour:
                if entry["quantity"] < quantity:
                    return False

                entry["quantity"] -= quantity
                entry["last_updated"] = datetime.utcnow().isoformat() + "Z"

                # Log usage
                usage = {
                    "date": datetime.utcnow().isoformat() + "Z",
                    "screw_type": screw_type,
                    "colour": colour,
                    "quantity": quantity,
                    "reason": reason,
                    "order_id": order_id
                }
                self.data["usage_history"].append(usage)

                self._save_data()
                return True

        return False

    def get_stock(self, screw_type: Optional[str] = None, colour: Optional[str] = None) -> list:
        """
        Get current screw stock.

        Args:
            screw_type: Filter by type (optional)
            colour: Filter by colour (optional)

        Returns:
            List of stock entries
        """
        stock = self.data["inventory"]
        if screw_type:
            stock = [s for s in stock if s["screw_type"] == screw_type]
        if colour:
            stock = [s for s in stock if s["colour"] == colour]
        return stock

    def get_stock_summary(self) -> list:
        """Get summarized stock by screw type and colour."""
        summary = []
        for entry in self.data["inventory"]:
            if entry["quantity"] > 0:
                summary.append({
                    "screw_type": entry["screw_type"],
                    "colour": entry["colour"],
                    "quantity": entry["quantity"],
                    "boxes": entry["quantity"] // self.config["pack_size"]
                })
        return summary

    def get_stock_by_type_and_colour(self, screw_type: str, colour: str) -> int:
        """Get quantity for a specific screw type and colour."""
        for entry in self.data["inventory"]:
            if entry["screw_type"] == screw_type and entry["colour"] == colour:
                return entry["quantity"]
        return 0

    # -------------------------
    # Utility
    # -------------------------

    def get_screw_types(self) -> dict:
        """Get screw type configurations."""
        return self.config["screw_types"]

    def get_colours(self) -> list:
        """Get available colours."""
        return self.config["colours"]

    def get_pack_size(self) -> int:
        """Get pack/box size."""
        return self.config["pack_size"]

    def get_supplier(self) -> str:
        """Get supplier name."""
        return self.config.get("supplier", "")


# Command-line interface for testing
if __name__ == "__main__":
    manager = ScrewManager()

    print("Screw Manager CLI")
    print("=" * 40)
    print(f"Screw types: {list(manager.get_screw_types().keys())}")
    print(f"Colours: {len(manager.get_colours())} available")
    print(f"Pack size: {manager.get_pack_size()}")
    print(f"Supplier: {manager.get_supplier()}")
    print()

    # Show current stock
    stock = manager.get_stock_summary()
    print(f"Current stock entries: {len(stock)}")
    for item in stock:
        print(f"  {item['screw_type']} ({item['colour']}): {item['quantity']:,} ({item['boxes']} boxes)")
