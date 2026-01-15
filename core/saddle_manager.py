"""
Saddle Production Manager

Tracks steel coils, production runs, and ready saddle stock.
Handles coil → saddle conversion with waste tracking.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional
import uuid

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "saddle_config.json")
COIL_DATA_PATH = os.path.join(BASE_DIR, "data", "coil_inventory.json")
SADDLE_DATA_PATH = os.path.join(BASE_DIR, "data", "saddle_stock.json")


class SaddleManager:
    """Manages coil inventory, saddle production, and ready stock."""

    def __init__(self):
        self.config = self._load_config()
        self.coil_data = self._load_coil_data()
        self.saddle_data = self._load_saddle_data()

    def _load_config(self) -> dict:
        """Load saddle configuration."""
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)

    def _load_coil_data(self) -> dict:
        """Load coil inventory data."""
        with open(COIL_DATA_PATH, "r") as f:
            return json.load(f)

    def _load_saddle_data(self) -> dict:
        """Load saddle stock data."""
        with open(SADDLE_DATA_PATH, "r") as f:
            return json.load(f)

    def _save_coil_data(self):
        """Save coil inventory data."""
        self.coil_data["last_updated"] = datetime.utcnow().isoformat() + "Z"
        with open(COIL_DATA_PATH, "w") as f:
            json.dump(self.coil_data, f, indent=2)

    def _save_saddle_data(self):
        """Save saddle stock data."""
        self.saddle_data["last_updated"] = datetime.utcnow().isoformat() + "Z"
        with open(SADDLE_DATA_PATH, "w") as f:
            json.dump(self.saddle_data, f, indent=2)

    # -------------------------
    # Coil Management
    # -------------------------

    def add_coil(
        self,
        saddle_type: str,
        colour: str,
        weight_kg: float,
        supplier: str = "",
        received_date: Optional[str] = None,
        notes: str = ""
    ) -> dict:
        """
        Add a new steel coil to inventory.

        Args:
            saddle_type: 'corrugated', 'klip_lok'
            colour: Colorbond colour name
            weight_kg: Weight in kilograms (50-500kg typical)
            supplier: Supplier name
            received_date: Date received (YYYY-MM-DD)
            notes: Optional notes

        Returns:
            The created coil entry
        """
        if received_date is None:
            received_date = datetime.now().strftime("%Y-%m-%d")

        # Calculate estimated yield using type-specific values
        type_config = self.config["saddle_types"].get(saddle_type, {})
        yield_per_kg = type_config.get("yield_per_kg", self.config["production"]["yield_per_kg"])
        waste_percent = type_config.get("waste_percent", self.config["production"]["waste_percent"])
        usable_kg = weight_kg * (1 - waste_percent / 100)
        estimated_yield = int(usable_kg * yield_per_kg)

        entry = {
            "id": str(uuid.uuid4())[:8],
            "saddle_type": saddle_type,
            "colour": colour,
            "initial_weight_kg": weight_kg,
            "current_weight_kg": weight_kg,
            "estimated_yield": estimated_yield,
            "status": "in_stock",
            "supplier": supplier,
            "received_date": received_date,
            "notes": notes,
            "created_at": datetime.utcnow().isoformat() + "Z"
        }

        self.coil_data["inventory"].append(entry)
        self._save_coil_data()
        return entry

    def get_coil_inventory(
        self,
        saddle_type: Optional[str] = None,
        colour: Optional[str] = None,
        status: Optional[str] = None
    ) -> list:
        """
        Get coil inventory with optional filters.

        Args:
            saddle_type: Filter by saddle type
            colour: Filter by colour
            status: Filter by status ('in_stock', 'in_use', 'depleted')

        Returns:
            List of coil entries matching filters
        """
        coils = self.coil_data["inventory"]

        if saddle_type:
            coils = [c for c in coils if c["saddle_type"] == saddle_type]
        if colour:
            coils = [c for c in coils if c["colour"] == colour]
        if status:
            coils = [c for c in coils if c["status"] == status]

        return coils

    def get_available_coils(self, saddle_type: Optional[str] = None) -> list:
        """Get coils that still have material (in_stock or in_use)."""
        coils = self.get_coil_inventory(saddle_type=saddle_type)
        return [c for c in coils if c["current_weight_kg"] > 0]

    # -------------------------
    # Production
    # -------------------------

    def log_production(
        self,
        coil_id: str,
        weight_used_kg: float,
        saddles_produced: Optional[int] = None,
        operator: str = "",
        notes: str = ""
    ) -> dict:
        """
        Log a production run (pressing saddles from a coil).

        Args:
            coil_id: ID of the coil used
            weight_used_kg: Amount of coil used (kg)
            saddles_produced: Actual count (auto-calculated if not provided)
            operator: Name of operator
            notes: Optional notes

        Returns:
            Production run record

        Raises:
            ValueError: If coil not found or insufficient material
        """
        # Find coil
        coil = None
        for c in self.coil_data["inventory"]:
            if c["id"] == coil_id:
                coil = c
                break

        if not coil:
            raise ValueError(f"Coil not found: {coil_id}")

        if weight_used_kg > coil["current_weight_kg"]:
            raise ValueError(
                f"Insufficient material. Coil has {coil['current_weight_kg']}kg, "
                f"requested {weight_used_kg}kg"
            )

        # Calculate production using type-specific yield/waste
        saddle_type = coil["saddle_type"]
        type_config = self.config["saddle_types"].get(saddle_type, {})
        yield_per_kg = type_config.get("yield_per_kg", self.config["production"]["yield_per_kg"])
        waste_percent = type_config.get("waste_percent", self.config["production"]["waste_percent"])

        usable_kg = weight_used_kg * (1 - waste_percent / 100)
        waste_kg = weight_used_kg * (waste_percent / 100)
        expected_saddles = int(usable_kg * yield_per_kg)

        # Use actual count if provided, otherwise use calculated
        if saddles_produced is None:
            saddles_produced = expected_saddles

        # Update coil
        coil["current_weight_kg"] -= weight_used_kg
        if coil["current_weight_kg"] <= 0:
            coil["status"] = "depleted"
        else:
            coil["status"] = "in_use"

        # Create production record
        production_record = {
            "id": str(uuid.uuid4())[:8],
            "date": datetime.utcnow().isoformat() + "Z",
            "coil_id": coil_id,
            "saddle_type": coil["saddle_type"],
            "colour": coil["colour"],
            "weight_used_kg": weight_used_kg,
            "usable_kg": round(usable_kg, 2),
            "waste_kg": round(waste_kg, 2),
            "expected_saddles": expected_saddles,
            "saddles_produced": saddles_produced,
            "operator": operator,
            "notes": notes
        }

        # Add to production history
        self.saddle_data["production_history"].append(production_record)

        # Add saddles to stock
        self._add_to_stock(
            saddle_type=coil["saddle_type"],
            colour=coil["colour"],
            quantity=saddles_produced,
            source="production",
            production_id=production_record["id"]
        )

        # Save both data files
        self._save_coil_data()
        self._save_saddle_data()

        return production_record

    def calculate_production_estimate(self, weight_kg: float, saddle_type: Optional[str] = None) -> dict:
        """
        Calculate expected production from a given weight.

        Args:
            weight_kg: Weight of material to process
            saddle_type: Type of coil (corrugated, trim) - uses type-specific yield if provided

        Returns:
            Dict with usable_kg, waste_kg, expected output
        """
        # Get type-specific yield/waste if saddle_type provided
        if saddle_type and saddle_type in self.config["saddle_types"]:
            type_config = self.config["saddle_types"][saddle_type]
            yield_per_kg = type_config.get("yield_per_kg", self.config["production"]["yield_per_kg"])
            waste_percent = type_config.get("waste_percent", self.config["production"]["waste_percent"])
            output_unit = type_config.get("output_unit", "saddles")
        else:
            yield_per_kg = self.config["production"]["yield_per_kg"]
            waste_percent = self.config["production"]["waste_percent"]
            output_unit = "saddles"

        usable_kg = weight_kg * (1 - waste_percent / 100)
        waste_kg = weight_kg * (waste_percent / 100)
        expected_output = int(usable_kg * yield_per_kg)

        return {
            "weight_kg": weight_kg,
            "usable_kg": round(usable_kg, 2),
            "waste_kg": round(waste_kg, 2),
            "waste_percent": waste_percent,
            "expected_saddles": expected_output,  # Keep key name for compatibility
            "expected_output": expected_output,
            "output_unit": output_unit,
            "yield_per_kg": yield_per_kg
        }

    def get_production_history(self, days: int = 90) -> list:
        """Get production history for the last N days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        history = []

        for record in self.saddle_data.get("production_history", []):
            # Parse as naive datetime (strip Z suffix)
            prod_date = datetime.fromisoformat(record["date"].replace("Z", ""))
            if prod_date >= cutoff:
                history.append(record)

        return sorted(history, key=lambda x: x["date"], reverse=True)

    # -------------------------
    # Saddle Stock Management
    # -------------------------

    def _add_to_stock(
        self,
        saddle_type: str,
        colour: str,
        quantity: int,
        source: str = "production",
        production_id: Optional[str] = None
    ):
        """Internal method to add saddles to stock."""
        # Find existing entry or create new
        for entry in self.saddle_data["inventory"]:
            if entry["saddle_type"] == saddle_type and entry["colour"] == colour:
                entry["quantity"] += quantity
                entry["last_updated"] = datetime.utcnow().isoformat() + "Z"
                return

        # Create new entry
        entry = {
            "id": str(uuid.uuid4())[:8],
            "saddle_type": saddle_type,
            "colour": colour,
            "quantity": quantity,
            "source": source,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "last_updated": datetime.utcnow().isoformat() + "Z"
        }
        self.saddle_data["inventory"].append(entry)

    def add_saddles(
        self,
        saddle_type: str,
        colour: str,
        quantity: int,
        source: str = "external",
        notes: str = ""
    ) -> dict:
        """
        Add finished saddles to stock (for TrimDek or manual adjustments).

        Args:
            saddle_type: 'corrugated', 'klip_lok', 'trimdek'
            colour: Colorbond colour name
            quantity: Number of saddles to add
            source: 'external', 'adjustment', etc.
            notes: Optional notes

        Returns:
            Updated or created stock entry
        """
        self._add_to_stock(saddle_type, colour, quantity, source)
        self._save_saddle_data()

        # Return the updated entry
        for entry in self.saddle_data["inventory"]:
            if entry["saddle_type"] == saddle_type and entry["colour"] == colour:
                return entry

    def remove_saddles(
        self,
        saddle_type: str,
        colour: str,
        quantity: int,
        reason: str = "order",
        order_id: Optional[str] = None
    ) -> bool:
        """
        Remove saddles from stock (for orders or adjustments).

        Args:
            saddle_type: Type of saddle
            colour: Colour
            quantity: Number to remove
            reason: 'order', 'damaged', 'adjustment'
            order_id: Shopify order ID if applicable

        Returns:
            True if successful, False if insufficient stock
        """
        for entry in self.saddle_data["inventory"]:
            if entry["saddle_type"] == saddle_type and entry["colour"] == colour:
                if entry["quantity"] < quantity:
                    return False

                entry["quantity"] -= quantity
                entry["last_updated"] = datetime.utcnow().isoformat() + "Z"

                # Log usage
                usage = {
                    "date": datetime.utcnow().isoformat() + "Z",
                    "saddle_type": saddle_type,
                    "colour": colour,
                    "quantity": quantity,
                    "reason": reason,
                    "order_id": order_id
                }
                self.saddle_data["usage_history"].append(usage)

                self._save_saddle_data()
                return True

        return False

    def get_saddle_stock(
        self,
        saddle_type: Optional[str] = None,
        colour: Optional[str] = None
    ) -> list:
        """
        Get current saddle stock with optional filters.

        Returns:
            List of stock entries
        """
        stock = self.saddle_data["inventory"]

        if saddle_type:
            stock = [s for s in stock if s["saddle_type"] == saddle_type]
        if colour:
            stock = [s for s in stock if s["colour"] == colour]

        return [s for s in stock if s["quantity"] > 0]

    def get_stock_summary(self) -> list:
        """Get summarized stock by saddle type and colour."""
        summary = {}
        for entry in self.saddle_data["inventory"]:
            if entry["quantity"] > 0:
                key = (entry["saddle_type"], entry["colour"])
                if key not in summary:
                    summary[key] = {
                        "saddle_type": entry["saddle_type"],
                        "colour": entry["colour"],
                        "quantity": 0
                    }
                summary[key]["quantity"] += entry["quantity"]

        return list(summary.values())

    # -------------------------
    # Utility
    # -------------------------

    def get_colours(self) -> list:
        """Get list of available colours."""
        return self.config["colours"]

    def get_saddle_types(self) -> dict:
        """Get saddle type configurations."""
        return self.config["saddle_types"]

    def get_suppliers(self) -> list:
        """Get list of suppliers."""
        return self.config.get("suppliers", [])

    def get_production_config(self) -> dict:
        """Get production parameters (yield, waste)."""
        return self.config["production"]


# Command-line interface for testing
if __name__ == "__main__":
    manager = SaddleManager()

    print("Saddle Manager CLI")
    print("=" * 40)
    print(f"Config loaded: {len(manager.get_colours())} colours")
    print(f"Saddle types: {list(manager.get_saddle_types().keys())}")
    print(f"Production yield: {manager.get_production_config()['yield_per_kg']}/kg")
    print(f"Waste: {manager.get_production_config()['waste_percent']}%")
    print()

    # Show coil inventory
    coils = manager.get_coil_inventory()
    print(f"Coils in inventory: {len(coils)}")

    # Show saddle stock
    stock = manager.get_stock_summary()
    print(f"Saddle stock entries: {len(stock)}")
