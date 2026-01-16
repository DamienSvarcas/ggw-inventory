"""
Stocktake State Manager
Handles session state, progress tracking, and auto-save functionality.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# Path for saving progress (in data/ directory)
DATA_DIR = Path(__file__).parent.parent / "data"
PROGRESS_FILE = DATA_DIR / "stocktake_progress.json"


class StocktakeState:
    """Manages the state of the stocktake wizard."""

    def __init__(self):
        self.items: List[Dict[str, Any]] = []
        self.quantities: Dict[str, int] = {}  # item_id -> quantity
        self.current_index: int = 0
        self.categories: List[str] = []
        self.started_at: Optional[str] = None
        self.last_saved: Optional[str] = None

    def initialize(self, items: List[Dict[str, Any]], categories: List[str]):
        """Initialize the wizard with items to count."""
        self.items = items
        self.categories = categories
        self.quantities = {item["id"]: None for item in items}
        self.current_index = 0
        self.started_at = datetime.now().isoformat()
        self.last_saved = None

    def set_quantity(self, item_id: str, quantity: int):
        """Set the quantity for an item."""
        self.quantities[item_id] = quantity

    def get_quantity(self, item_id: str) -> Optional[int]:
        """Get the quantity for an item."""
        return self.quantities.get(item_id)

    def skip_current(self):
        """Skip the current item (set to 0)."""
        if self.current_index < len(self.items):
            item_id = self.items[self.current_index]["id"]
            self.quantities[item_id] = 0

    def next_item(self) -> bool:
        """Move to the next item. Returns False if at end."""
        if self.current_index < len(self.items) - 1:
            self.current_index += 1
            return True
        return False

    def previous_item(self) -> bool:
        """Move to the previous item. Returns False if at start."""
        if self.current_index > 0:
            self.current_index -= 1
            return True
        return False

    def go_to_item(self, index: int) -> bool:
        """Jump to a specific item index."""
        if 0 <= index < len(self.items):
            self.current_index = index
            return True
        return False

    def get_current_item(self) -> Optional[Dict[str, Any]]:
        """Get the current item."""
        if 0 <= self.current_index < len(self.items):
            return self.items[self.current_index]
        return None

    def get_progress(self) -> Dict[str, Any]:
        """Get progress statistics."""
        total = len(self.items)
        completed = sum(1 for q in self.quantities.values() if q is not None)
        return {
            "current": self.current_index + 1,
            "total": total,
            "completed": completed,
            "remaining": total - completed,
            "percent": (completed / total * 100) if total > 0 else 0
        }

    def get_category_progress(self) -> Dict[str, Dict[str, int]]:
        """Get progress by category."""
        progress = {}
        for item in self.items:
            cat = item["category"]
            if cat not in progress:
                progress[cat] = {"total": 0, "completed": 0}
            progress[cat]["total"] += 1
            if self.quantities.get(item["id"]) is not None:
                progress[cat]["completed"] += 1
        return progress

    def is_complete(self) -> bool:
        """Check if all items have been entered."""
        return all(q is not None for q in self.quantities.values())

    def get_summary(self) -> List[Dict[str, Any]]:
        """Get a summary of all entries for review."""
        summary = []
        for item in self.items:
            entry = item.copy()
            entry["quantity"] = self.quantities.get(item["id"])
            summary.append(entry)
        return summary

    def get_non_zero_entries(self) -> List[Dict[str, Any]]:
        """Get only entries with quantity > 0."""
        return [
            {**item, "quantity": self.quantities[item["id"]]}
            for item in self.items
            if self.quantities.get(item["id"], 0) > 0
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for saving."""
        return {
            "items": self.items,
            "quantities": self.quantities,
            "current_index": self.current_index,
            "categories": self.categories,
            "started_at": self.started_at,
            "last_saved": datetime.now().isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StocktakeState":
        """Create state from saved dictionary."""
        state = cls()
        state.items = data.get("items", [])
        state.quantities = data.get("quantities", {})
        state.current_index = data.get("current_index", 0)
        state.categories = data.get("categories", [])
        state.started_at = data.get("started_at")
        state.last_saved = data.get("last_saved")
        return state

    def save_progress(self) -> bool:
        """Save progress to file."""
        try:
            with open(PROGRESS_FILE, "w") as f:
                json.dump(self.to_dict(), f, indent=2)
            self.last_saved = datetime.now().isoformat()
            return True
        except Exception as e:
            print(f"Error saving progress: {e}")
            return False

    @classmethod
    def load_progress(cls) -> Optional["StocktakeState"]:
        """Load progress from file if it exists."""
        if not PROGRESS_FILE.exists():
            return None
        try:
            with open(PROGRESS_FILE, "r") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as e:
            print(f"Error loading progress: {e}")
            return None

    @classmethod
    def clear_progress(cls):
        """Clear saved progress."""
        if PROGRESS_FILE.exists():
            PROGRESS_FILE.unlink()

    @classmethod
    def has_saved_progress(cls) -> bool:
        """Check if there is saved progress."""
        return PROGRESS_FILE.exists()

    @classmethod
    def get_saved_progress_info(cls) -> Optional[Dict[str, Any]]:
        """Get info about saved progress without loading full state."""
        if not PROGRESS_FILE.exists():
            return None
        try:
            with open(PROGRESS_FILE, "r") as f:
                data = json.load(f)
            completed = sum(1 for q in data.get("quantities", {}).values() if q is not None)
            total = len(data.get("items", []))
            return {
                "started_at": data.get("started_at"),
                "last_saved": data.get("last_saved"),
                "completed": completed,
                "total": total,
                "categories": data.get("categories", [])
            }
        except Exception:
            return None
