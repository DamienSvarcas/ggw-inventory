"""
Inventory Updater
Writes stocktake results to the inventory JSON files.
Preserves incoming_orders and production_history.
"""

import json
import shutil
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Path to data files
DATA_DIR = Path(__file__).parent.parent / "data"
BACKUP_DIR = Path(__file__).parent / "backups"


def generate_id() -> str:
    """Generate a short unique ID."""
    return uuid.uuid4().hex[:8]


def get_timestamp() -> str:
    """Get current ISO timestamp."""
    return datetime.utcnow().isoformat() + "Z"


def create_backup():
    """Create backup of all data files before updating."""
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_subdir = BACKUP_DIR / f"stocktake_{timestamp}"
    backup_subdir.mkdir(exist_ok=True)

    files_to_backup = [
        "mesh_rolls.json",
        "screw_inventory.json",
        "box_inventory.json",
        "saddle_stock.json",
        "trim_inventory.json"
    ]

    for filename in files_to_backup:
        src = DATA_DIR / filename
        if src.exists():
            shutil.copy2(src, backup_subdir / filename)

    return backup_subdir


def load_data_file(filename: str) -> Dict[str, Any]:
    """Load a data file."""
    filepath = DATA_DIR / filename
    if filepath.exists():
        with open(filepath, "r") as f:
            return json.load(f)
    return {}


def save_data_file(filename: str, data: Dict[str, Any]):
    """Save data to file."""
    filepath = DATA_DIR / filename
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def update_screw_inventory(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Update screw inventory from stocktake entries.
    Screws category - one per colour, boxes of 1000.
    """
    existing = load_data_file("screw_inventory.json")

    new_inventory = []
    timestamp = get_timestamp()

    for entry in entries:
        if entry["category"] != "screws" or entry.get("quantity", 0) <= 0:
            continue

        new_inventory.append({
            "id": generate_id(),
            "screw_type": "screws",
            "colour": entry["colour"],
            "quantity": entry["quantity"],
            "unit": "screws",
            "box_size": 1000,
            "source": "stocktake",
            "created_at": timestamp,
            "last_updated": timestamp
        })

    updated = {
        "last_updated": timestamp,
        "inventory": new_inventory,
        "usage_history": [],
        "notes": existing.get("notes", "Screw inventory by colour.")
    }

    save_data_file("screw_inventory.json", updated)

    return {
        "file": "screw_inventory.json",
        "category": "screws",
        "items_added": len(new_inventory),
        "previous_items": len(existing.get("inventory", []))
    }


def update_trim_inventory(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Update trim inventory from stocktake entries.
    Trims - one per colour.
    """
    existing = load_data_file("trim_inventory.json")

    new_inventory = []
    timestamp = get_timestamp()

    for entry in entries:
        if entry["category"] != "trims" or entry.get("quantity", 0) <= 0:
            continue

        new_inventory.append({
            "id": generate_id(),
            "colour": entry["colour"],
            "quantity": entry["quantity"],
            "unit": "trims",
            "source": "stocktake",
            "created_at": timestamp,
            "last_updated": timestamp
        })

    updated = {
        "last_updated": timestamp,
        "inventory": new_inventory,
        "usage_history": [],
        "notes": existing.get("notes", "Trim inventory by colour.")
    }

    save_data_file("trim_inventory.json", updated)

    return {
        "file": "trim_inventory.json",
        "category": "trims",
        "items_added": len(new_inventory),
        "previous_items": len(existing.get("inventory", []))
    }


def update_saddle_inventory(entries: List[Dict[str, Any]], saddle_type: str) -> Dict[str, Any]:
    """
    Update saddle inventory from stocktake entries for a specific saddle type.
    Preserves production_history and entries of other saddle type.

    Args:
        entries: List of saddle entries
        saddle_type: Either "corrugated" or "trimdek"
    """
    existing = load_data_file("saddle_stock.json")
    timestamp = get_timestamp()

    # Determine which category to look for
    if saddle_type == "corrugated":
        category_name = "corrugated_saddles"
    else:
        category_name = "trimdek_saddles"

    # Keep existing inventory for OTHER saddle type
    other_type = "trimdek" if saddle_type == "corrugated" else "corrugated"
    kept_inventory = [
        item for item in existing.get("inventory", [])
        if item.get("saddle_type") == other_type
    ]

    # Build new inventory for this saddle type
    new_entries = []
    for entry in entries:
        if entry["category"] != category_name or entry.get("quantity", 0) <= 0:
            continue

        new_entries.append({
            "id": generate_id(),
            "saddle_type": saddle_type,
            "colour": entry["colour"],
            "quantity": entry["quantity"],
            "source": "stocktake",
            "created_at": timestamp,
            "last_updated": timestamp
        })

    # Combine: kept entries from other type + new entries for this type
    combined_inventory = kept_inventory + new_entries

    updated = {
        "last_updated": timestamp,
        "inventory": combined_inventory,
        "production_history": existing.get("production_history", []),
        "usage_history": [],
        "notes": existing.get("notes", "Ready saddle stock by type and colour.")
    }

    save_data_file("saddle_stock.json", updated)

    return {
        "file": "saddle_stock.json",
        "category": category_name,
        "saddle_type": saddle_type,
        "items_added": len(new_entries),
        "previous_items": len([
            i for i in existing.get("inventory", [])
            if i.get("saddle_type") == saddle_type
        ]),
        "production_history_preserved": len(existing.get("production_history", []))
    }


def update_box_inventory(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Update box inventory from stocktake entries.
    3 box types.
    """
    existing = load_data_file("box_inventory.json")

    new_inventory = []
    timestamp = get_timestamp()

    for entry in entries:
        if entry["category"] != "boxes" or entry.get("quantity", 0) <= 0:
            continue

        new_inventory.append({
            "id": generate_id(),
            "box_type": entry["box_type"],
            "quantity": entry["quantity"],
            "source": "stocktake",
            "created_at": timestamp,
            "last_updated": timestamp
        })

    updated = {
        "last_updated": timestamp,
        "inventory": new_inventory,
        "usage_history": [],
        "notes": existing.get("notes", "Box inventory by type.")
    }

    save_data_file("box_inventory.json", updated)

    return {
        "file": "box_inventory.json",
        "category": "boxes",
        "items_added": len(new_inventory),
        "previous_items": len(existing.get("inventory", []))
    }


def update_mesh_inventory(entries: List[Dict[str, Any]], mesh_category: str) -> Dict[str, Any]:
    """
    Update mesh roll inventory from stocktake entries for a specific mesh type.
    PRESERVES incoming_orders (4-month turnaround items).
    Preserves entries of other mesh type.

    Args:
        entries: List of mesh entries
        mesh_category: Either "mesh_4mm" or "mesh_2mm"
    """
    existing = load_data_file("mesh_rolls.json")
    timestamp = get_timestamp()
    today = datetime.now().strftime("%Y-%m-%d")

    # Determine mesh type
    if mesh_category == "mesh_4mm":
        mesh_type = "4mm_aluminium"
    else:
        mesh_type = "2mm_ember_guard"

    # Keep existing inventory for OTHER mesh type
    other_type = "2mm_ember_guard" if mesh_type == "4mm_aluminium" else "4mm_aluminium"
    kept_inventory = [
        item for item in existing.get("inventory", [])
        if item.get("mesh_type") == other_type
    ]

    # Build new inventory for this mesh type
    new_entries = []
    for entry in entries:
        if entry["category"] != mesh_category or entry.get("quantity", 0) <= 0:
            continue

        new_entries.append({
            "id": generate_id(),
            "mesh_type": mesh_type,
            "width_mm": entry["width_mm"],
            "length_m": entry["length_m"],
            "colour": entry["colour"],
            "quantity": entry["quantity"],
            "received_date": today,
            "location": "Warehouse",
            "notes": "From stocktake",
            "created_at": timestamp
        })

    # Combine: kept entries from other type + new entries for this type
    combined_inventory = kept_inventory + new_entries

    updated = {
        "last_updated": timestamp,
        "inventory": combined_inventory,
        "usage_history": [],
        "incoming_orders": existing.get("incoming_orders", []),
        "notes": existing.get("notes", "Mesh roll inventory.")
    }

    save_data_file("mesh_rolls.json", updated)

    return {
        "file": "mesh_rolls.json",
        "category": mesh_category,
        "mesh_type": mesh_type,
        "items_added": len(new_entries),
        "previous_items": len([
            i for i in existing.get("inventory", [])
            if i.get("mesh_type") == mesh_type
        ]),
        "incoming_orders_preserved": len(existing.get("incoming_orders", []))
    }


def apply_category_stocktake(entries: List[Dict[str, Any]], category: str) -> Dict[str, Any]:
    """
    Apply stocktake for a single category.

    Args:
        entries: List of entries with quantities for this category
        category: Category name (screws, trims, corrugated_saddles, trimdek_saddles,
                  boxes, mesh_4mm, mesh_2mm)

    Returns:
        Summary of update
    """
    # Create backup first
    backup_path = create_backup()

    # Filter to non-zero entries
    non_zero_entries = [e for e in entries if e.get("quantity", 0) > 0]

    result = {
        "backup_location": str(backup_path),
        "timestamp": get_timestamp(),
        "category": category,
        "update": None
    }

    if category == "screws":
        result["update"] = update_screw_inventory(non_zero_entries)
    elif category == "trims":
        result["update"] = update_trim_inventory(non_zero_entries)
    elif category == "corrugated_saddles":
        result["update"] = update_saddle_inventory(non_zero_entries, "corrugated")
    elif category == "trimdek_saddles":
        result["update"] = update_saddle_inventory(non_zero_entries, "trimdek")
    elif category == "boxes":
        result["update"] = update_box_inventory(non_zero_entries)
    elif category == "mesh_4mm":
        result["update"] = update_mesh_inventory(non_zero_entries, "mesh_4mm")
    elif category == "mesh_2mm":
        result["update"] = update_mesh_inventory(non_zero_entries, "mesh_2mm")

    return result


def apply_stocktake(entries: List[Dict[str, Any]], categories: List[str] = None) -> Dict[str, Any]:
    """
    Apply stocktake entries to inventory files.

    Args:
        entries: List of all entries with quantities
        categories: Optional list of categories to update. If None, updates all.

    Returns:
        Summary of all updates
    """
    # Create backup first
    backup_path = create_backup()

    # Filter to only entries with quantity > 0
    non_zero_entries = [e for e in entries if e.get("quantity", 0) > 0]

    # Determine which categories to update
    if categories is None:
        categories = ['screws', 'trims', 'corrugated_saddles', 'trimdek_saddles',
                      'boxes', 'mesh_4mm', 'mesh_2mm']

    results = {
        "backup_location": str(backup_path),
        "timestamp": get_timestamp(),
        "updates": []
    }

    # Update each category
    if 'screws' in categories:
        results["updates"].append(update_screw_inventory(non_zero_entries))

    if 'trims' in categories:
        results["updates"].append(update_trim_inventory(non_zero_entries))

    if 'corrugated_saddles' in categories:
        results["updates"].append(update_saddle_inventory(non_zero_entries, "corrugated"))

    if 'trimdek_saddles' in categories:
        results["updates"].append(update_saddle_inventory(non_zero_entries, "trimdek"))

    if 'boxes' in categories:
        results["updates"].append(update_box_inventory(non_zero_entries))

    if 'mesh_4mm' in categories:
        results["updates"].append(update_mesh_inventory(non_zero_entries, "mesh_4mm"))

    if 'mesh_2mm' in categories:
        results["updates"].append(update_mesh_inventory(non_zero_entries, "mesh_2mm"))

    return results


def restore_from_backup(backup_dir: str) -> bool:
    """
    Restore inventory files from a backup.

    Args:
        backup_dir: Path to the backup directory

    Returns:
        True if successful
    """
    backup_path = Path(backup_dir)
    if not backup_path.exists():
        return False

    files = [
        "mesh_rolls.json",
        "screw_inventory.json",
        "box_inventory.json",
        "saddle_stock.json",
        "trim_inventory.json"
    ]

    for filename in files:
        src = backup_path / filename
        if src.exists():
            shutil.copy2(src, DATA_DIR / filename)

    return True


def list_backups() -> List[Dict[str, Any]]:
    """List available backups."""
    if not BACKUP_DIR.exists():
        return []

    backups = []
    for d in sorted(BACKUP_DIR.iterdir(), reverse=True):
        if d.is_dir() and d.name.startswith("stocktake_"):
            files = list(d.glob("*.json"))
            backups.append({
                "name": d.name,
                "path": str(d),
                "files": len(files),
                "timestamp": d.name.replace("stocktake_", "")
            })

    return backups
