"""
Box Inventory Manager

Tracks box stock by type (small tube, large tube, flat pack).
Simple add/remove stock management.
"""

import json
import os
from datetime import datetime
from typing import Optional
import uuid

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "box_config.json")
DATA_PATH = os.path.join(BASE_DIR, "data", "box_inventory.json")


class BoxManager:
    """Manages box inventory by type."""

    def __init__(self):
        self.config = self._load_config()
        self.data = self._load_data()

    def _load_config(self) -> dict:
        """Load box configuration."""
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)

    def _load_data(self) -> dict:
        """Load box inventory data."""
        with open(DATA_PATH, "r") as f:
            return json.load(f)

    def _save_data(self):
        """Save box inventory data."""
        self.data["last_updated"] = datetime.utcnow().isoformat() + "Z"
        with open(DATA_PATH, "w") as f:
            json.dump(self.data, f, indent=2)

    # -------------------------
    # Stock Management
    # -------------------------

    def add_stock(
        self,
        box_type: str,
        quantity: int,
        source: str = "received",
        notes: str = ""
    ) -> dict:
        """
        Add boxes to inventory.

        Args:
            box_type: 'small_tube', 'large_tube', 'flat_pack'
            quantity: Number of boxes to add
            source: 'received', 'adjustment', 'return'
            notes: Optional notes

        Returns:
            Updated stock entry
        """
        # Find existing entry or create new
        for entry in self.data["inventory"]:
            if entry["box_type"] == box_type:
                entry["quantity"] += quantity
                entry["last_updated"] = datetime.utcnow().isoformat() + "Z"
                self._save_data()
                return entry

        # Create new entry
        entry = {
            "id": str(uuid.uuid4())[:8],
            "box_type": box_type,
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
        box_type: str,
        quantity: int,
        reason: str = "order",
        order_id: Optional[str] = None
    ) -> bool:
        """
        Remove boxes from inventory.

        Args:
            box_type: Type of box
            quantity: Number to remove
            reason: 'order', 'damaged', 'adjustment'
            order_id: Shopify order ID if applicable

        Returns:
            True if successful, False if insufficient stock
        """
        for entry in self.data["inventory"]:
            if entry["box_type"] == box_type:
                if entry["quantity"] < quantity:
                    return False

                entry["quantity"] -= quantity
                entry["last_updated"] = datetime.utcnow().isoformat() + "Z"

                # Log usage
                usage = {
                    "date": datetime.utcnow().isoformat() + "Z",
                    "box_type": box_type,
                    "quantity": quantity,
                    "reason": reason,
                    "order_id": order_id
                }
                self.data["usage_history"].append(usage)

                self._save_data()
                return True

        return False

    def get_stock(self, box_type: Optional[str] = None) -> list:
        """
        Get current box stock.

        Args:
            box_type: Filter by type (optional)

        Returns:
            List of stock entries
        """
        stock = self.data["inventory"]
        if box_type:
            stock = [s for s in stock if s["box_type"] == box_type]
        return stock

    def get_stock_summary(self) -> list:
        """Get summarized stock by box type."""
        summary = []
        for entry in self.data["inventory"]:
            if entry["quantity"] > 0:
                box_config = self.config["box_types"].get(entry["box_type"], {})
                pack_size = box_config.get("pack_size", 1)
                summary.append({
                    "box_type": entry["box_type"],
                    "quantity": entry["quantity"],
                    "packs": entry["quantity"] // pack_size,
                    "loose": entry["quantity"] % pack_size
                })
        return summary

    def get_stock_by_type(self, box_type: str) -> int:
        """Get quantity for a specific box type."""
        for entry in self.data["inventory"]:
            if entry["box_type"] == box_type:
                return entry["quantity"]
        return 0

    # -------------------------
    # Utility
    # -------------------------

    def get_box_types(self) -> dict:
        """Get box type configurations."""
        return self.config["box_types"]

    def get_pack_size(self, box_type: str) -> int:
        """Get pack size for a box type."""
        return self.config["box_types"].get(box_type, {}).get("pack_size", 1)

    def get_supplier(self) -> str:
        """Get supplier name."""
        return self.config.get("supplier", "")


# Command-line interface for testing
if __name__ == "__main__":
    manager = BoxManager()

    print("Box Manager CLI")
    print("=" * 40)
    print(f"Box types: {list(manager.get_box_types().keys())}")
    print(f"Supplier: {manager.get_supplier()}")
    print()

    # Show current stock
    stock = manager.get_stock_summary()
    print(f"Current stock entries: {len(stock)}")
    for item in stock:
        print(f"  {item['box_type']}: {item['quantity']:,} ({item['packs']} packs + {item['loose']} loose)")
