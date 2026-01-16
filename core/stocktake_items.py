"""
Stocktake Item Generator
Generates the full list of items to count from config files.
"""

import json
from pathlib import Path
from typing import List, Dict, Any

# Path to config files
CONFIG_DIR = Path(__file__).parent.parent / "config"


def load_config(filename: str) -> Dict[str, Any]:
    """Load a config file."""
    config_path = CONFIG_DIR / filename
    with open(config_path, "r") as f:
        return json.load(f)


def generate_screw_items() -> List[Dict[str, Any]]:
    """Generate screw items - one per colour (boxes of 1000)."""
    config = load_config("screw_config.json")
    items = []

    # Sort colours alphabetically
    colours = sorted(config["colours"])

    for colour in colours:
        items.append({
            "category": "screws",
            "type_name": "Screws",
            "colour": colour,
            "unit": "boxes",
            "box_size": 1000,
            "id": f"screw_{colour.lower().replace(' ', '_')}"
        })

    return items


def generate_trim_items() -> List[Dict[str, Any]]:
    """Generate trim items - one per colour."""
    config = load_config("saddle_config.json")
    items = []

    # Sort colours alphabetically
    colours = sorted(config["colours"])

    for colour in colours:
        items.append({
            "category": "trims",
            "type_name": "Trims",
            "colour": colour,
            "unit": "trims",
            "id": f"trim_{colour.lower().replace(' ', '_')}"
        })

    return items


def generate_corrugated_saddle_items() -> List[Dict[str, Any]]:
    """Generate corrugated saddle items - one per colour."""
    config = load_config("saddle_config.json")
    items = []

    # Sort colours alphabetically
    colours = sorted(config["colours"])

    for colour in colours:
        items.append({
            "category": "corrugated_saddles",
            "type_name": "Corrugated Saddles",
            "colour": colour,
            "unit": "saddles",
            "id": f"corrugated_saddle_{colour.lower().replace(' ', '_')}"
        })

    return items


def generate_trimdek_saddle_items() -> List[Dict[str, Any]]:
    """Generate trimdek saddle items - one per colour."""
    config = load_config("saddle_config.json")
    items = []

    # Sort colours alphabetically
    colours = sorted(config["colours"])

    for colour in colours:
        items.append({
            "category": "trimdek_saddles",
            "type_name": "Trimdek Saddles",
            "colour": colour,
            "unit": "saddles",
            "id": f"trimdek_saddle_{colour.lower().replace(' ', '_')}"
        })

    return items


def generate_box_items() -> List[Dict[str, Any]]:
    """Generate box items - 3 types."""
    config = load_config("box_config.json")
    items = []

    for box_type, type_info in config["box_types"].items():
        items.append({
            "category": "boxes",
            "box_type": box_type,
            "type_name": type_info["name"],
            "description": type_info["description"],
            "colour": None,
            "unit": "boxes",
            "pack_size": type_info["pack_size"],
            "id": f"box_{box_type}"
        })

    return items


def generate_mesh_4mm_items() -> List[Dict[str, Any]]:
    """Generate 4mm mesh items - sorted by colour, then all sizes for that colour."""
    config = load_config("mesh_config.json")
    items = []

    mesh_type = "4mm_aluminium"
    type_info = config["mesh_types"][mesh_type]

    # Sort colours alphabetically
    colours = sorted(config["colours"])

    # For each colour, list all size options
    for colour in colours:
        for width in type_info["widths"]:
            for length in type_info["lengths"]:
                items.append({
                    "category": "mesh_4mm",
                    "mesh_type": mesh_type,
                    "type_name": "4mm Aluminium Mesh",
                    "width_mm": width,
                    "length_m": length,
                    "colour": colour,
                    "unit": "rolls",
                    "id": f"mesh_4mm_{width}_{length}_{colour.lower().replace(' ', '_')}"
                })

    return items


def generate_mesh_2mm_items() -> List[Dict[str, Any]]:
    """Generate 2mm ember mesh items - sorted by colour, then all sizes for that colour."""
    config = load_config("mesh_config.json")
    items = []

    mesh_type = "2mm_ember_guard"
    type_info = config["mesh_types"][mesh_type]

    # Sort colours alphabetically
    colours = sorted(config["colours"])

    # For each colour, list all size options
    for colour in colours:
        for width in type_info["widths"]:
            for length in type_info["lengths"]:
                items.append({
                    "category": "mesh_2mm",
                    "mesh_type": mesh_type,
                    "type_name": "2mm Ember Guard Mesh",
                    "width_mm": width,
                    "length_m": length,
                    "colour": colour,
                    "unit": "rolls",
                    "id": f"mesh_2mm_{width}_{length}_{colour.lower().replace(' ', '_')}"
                })

    return items


def generate_all_items(categories: List[str] = None) -> List[Dict[str, Any]]:
    """
    Generate all items for the stocktake wizard.

    Args:
        categories: List of categories to include. If None, include all.
                   Options: ['screws', 'trims', 'corrugated_saddles', 'trimdek_saddles',
                            'boxes', 'mesh_4mm', 'mesh_2mm']

    Returns:
        List of item dictionaries with all details needed for entry.
    """
    if categories is None:
        categories = ['screws', 'trims', 'corrugated_saddles', 'trimdek_saddles',
                      'boxes', 'mesh_4mm', 'mesh_2mm']

    all_items = []

    if 'screws' in categories:
        all_items.extend(generate_screw_items())

    if 'trims' in categories:
        all_items.extend(generate_trim_items())

    if 'corrugated_saddles' in categories:
        all_items.extend(generate_corrugated_saddle_items())

    if 'trimdek_saddles' in categories:
        all_items.extend(generate_trimdek_saddle_items())

    if 'boxes' in categories:
        all_items.extend(generate_box_items())

    if 'mesh_4mm' in categories:
        all_items.extend(generate_mesh_4mm_items())

    if 'mesh_2mm' in categories:
        all_items.extend(generate_mesh_2mm_items())

    return all_items


def get_category_counts() -> Dict[str, int]:
    """Get the count of items in each category."""
    return {
        'screws': len(generate_screw_items()),
        'trims': len(generate_trim_items()),
        'corrugated_saddles': len(generate_corrugated_saddle_items()),
        'trimdek_saddles': len(generate_trimdek_saddle_items()),
        'boxes': len(generate_box_items()),
        'mesh_4mm': len(generate_mesh_4mm_items()),
        'mesh_2mm': len(generate_mesh_2mm_items())
    }


# Category display names
CATEGORY_NAMES = {
    'screws': 'Screws',
    'trims': 'Trims',
    'corrugated_saddles': 'Corrugated Saddles',
    'trimdek_saddles': 'Trimdek Saddles',
    'boxes': 'Boxes',
    'mesh_4mm': '4mm Mesh',
    'mesh_2mm': '2mm Ember Mesh'
}


if __name__ == "__main__":
    # Test the generator
    counts = get_category_counts()
    print("Item counts by category:")
    for cat, count in counts.items():
        print(f"  {CATEGORY_NAMES.get(cat, cat)}: {count}")
    print(f"  TOTAL: {sum(counts.values())}")
