"""
Shopify Order Sync Module

Fetches order data from Shopify for usage analysis and forecasting.
"""

import json
import os
import requests
import time
from datetime import datetime, timedelta
from typing import Optional

# Shopify API Configuration (Streamlit secrets with env var fallback)
def _get_shopify_credentials():
    """Get Shopify credentials from Streamlit secrets or environment variables."""
    try:
        import streamlit as st
        store = st.secrets.get("shopify", {}).get("store", "")
        token = st.secrets.get("shopify", {}).get("token", "")
        if store and token:
            return store, token
    except Exception:
        pass
    # Fallback to environment variables
    return os.getenv("SHOPIFY_STORE", ""), os.getenv("SHOPIFY_TOKEN", "")

STORE, TOKEN = _get_shopify_credentials()
API_VERSION = "2024-01"
ENDPOINT = f"https://{STORE}/admin/api/{API_VERSION}/graphql.json"

HEADERS = {
    "Content-Type": "application/json",
    "X-Shopify-Access-Token": TOKEN
}

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(BASE_DIR, "data", "shopify_orders_cache.json")
KIT_BREAKDOWN_PATH = os.path.join(BASE_DIR, "config", "kit-component-breakdown.json")


class ShopifySync:
    """Syncs order data from Shopify for inventory forecasting."""

    def __init__(self):
        self.kit_breakdown = self._load_kit_breakdown()
        self.cached_orders = self._load_cache()

    def _load_kit_breakdown(self) -> dict:
        """Load kit component breakdown for mapping products to components."""
        try:
            with open(KIT_BREAKDOWN_PATH, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {"products": []}

    def _load_cache(self) -> dict:
        """Load cached orders if available."""
        try:
            with open(CACHE_PATH, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {"orders": [], "last_synced": None}

    def _save_cache(self, data: dict):
        """Save orders to cache."""
        with open(CACHE_PATH, "w") as f:
            json.dump(data, f, indent=2)

    def fetch_orders(
        self,
        days: int = 180,
        force_refresh: bool = False,
        progress_callback=None
    ) -> list:
        """
        Fetch orders from Shopify.

        Args:
            days: Number of days to fetch (default 180 = 6 months)
            force_refresh: If True, ignore cache and fetch fresh data
            progress_callback: Optional callback for progress updates

        Returns:
            List of order dictionaries with line items
        """
        # Check cache freshness (cache valid for 1 hour)
        if not force_refresh and self.cached_orders.get("last_synced"):
            last_synced = datetime.fromisoformat(
                self.cached_orders["last_synced"].replace("Z", "")
            )
            if datetime.utcnow() - last_synced < timedelta(hours=1):
                return self.cached_orders.get("orders", [])

        # Calculate date filter
        since_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

        all_orders = []
        cursor = None
        page = 1

        while True:
            if progress_callback:
                progress_callback(f"Fetching page {page}... ({len(all_orders)} orders so far)")

            result = self._fetch_orders_page(cursor, since_date)

            if "errors" in result:
                print(f"Shopify API error: {result['errors']}")
                break

            orders_data = result.get("data", {}).get("orders", {})
            edges = orders_data.get("edges", [])

            for edge in edges:
                node = edge["node"]
                order = self._parse_order(node)
                all_orders.append(order)

            page_info = orders_data.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break

            cursor = page_info.get("endCursor")
            page += 1
            time.sleep(0.5)  # Rate limiting

        # Cache results
        cache_data = {
            "last_synced": datetime.utcnow().isoformat() + "Z",
            "total_orders": len(all_orders),
            "days_fetched": days,
            "orders": all_orders
        }
        self._save_cache(cache_data)
        self.cached_orders = cache_data

        return all_orders

    def _fetch_orders_page(self, cursor: Optional[str], since_date: str) -> dict:
        """Fetch a single page of orders from Shopify."""
        after_clause = f', after: "{cursor}"' if cursor else ""

        query = f'''
        query {{
            orders(first: 50, query: "fulfillment_status:shipped created_at:>={since_date}", reverse: true{after_clause}) {{
                edges {{
                    node {{
                        name
                        createdAt
                        displayFulfillmentStatus
                        lineItems(first: 30) {{
                            edges {{
                                node {{
                                    title
                                    variant {{
                                        title
                                    }}
                                    quantity
                                    sku
                                }}
                            }}
                        }}
                    }}
                }}
                pageInfo {{
                    hasNextPage
                    endCursor
                }}
            }}
        }}
        '''

        response = requests.post(ENDPOINT, headers=HEADERS, json={"query": query})
        return response.json()

    def _parse_order(self, node: dict) -> dict:
        """Parse a Shopify order node into our format."""
        order = {
            "order_number": node["name"].replace("#", ""),
            "created_at": node["createdAt"],
            "status": node["displayFulfillmentStatus"],
            "line_items": []
        }

        for item_edge in node.get("lineItems", {}).get("edges", []):
            item = item_edge["node"]
            variant = item.get("variant", {})
            variant_title = variant.get("title", "") if variant else ""

            order["line_items"].append({
                "title": item["title"],
                "variant": variant_title,
                "quantity": item["quantity"],
                "sku": item.get("sku")
            })

        return order

    def calculate_component_usage(self, days: int = 180, force_refresh: bool = False,
                                    progress_callback=None) -> dict:
        """
        Calculate total component usage from orders.

        Returns dict with usage for each component type.
        """
        orders = self.fetch_orders(days=days, force_refresh=force_refresh,
                                   progress_callback=progress_callback)

        usage = {
            "mesh": [],  # List of {mesh_type, width_mm, length_m, quantity}
            "saddles": 0,
            "saddle_screws": 0,
            "trim_screws": 0,
            "mesh_screws": 0,
            "trims": 0,
            "order_count": len(orders),
            "period_days": days
        }

        for order in orders:
            for item in order["line_items"]:
                components = self._get_components_for_product(
                    item["title"],
                    item["variant"],
                    item["quantity"]
                )

                if components:
                    # Mesh
                    if "mesh" in components:
                        mesh = components["mesh"]
                        usage["mesh"].append({
                            "width_mm": mesh.get("width_mm", 250),
                            "length_m": mesh.get("length_m", 0) * item["quantity"]
                        })

                    # Other components
                    usage["saddles"] += components.get("saddles", 0) * item["quantity"]
                    usage["saddle_screws"] += components.get("saddle_screws", 0) * item["quantity"]
                    usage["trim_screws"] += components.get("trim_screws", 0) * item["quantity"]
                    usage["mesh_screws"] += components.get("mesh_screws", 0) * item["quantity"]
                    usage["trims"] += components.get("trims", 0) * item["quantity"]

        # Calculate daily averages
        if days > 0:
            usage["daily_avg"] = {
                "saddles": usage["saddles"] / days,
                "saddle_screws": usage["saddle_screws"] / days,
                "trim_screws": usage["trim_screws"] / days,
                "mesh_screws": usage["mesh_screws"] / days,
                "trims": usage["trims"] / days
            }

        return usage

    def _get_components_for_product(
        self,
        title: str,
        variant: str,
        quantity: int = 1
    ) -> Optional[dict]:
        """
        Look up components for a product from the kit breakdown.

        Args:
            title: Product title from Shopify
            variant: Variant title (e.g., "50m / Monument")
            quantity: Order quantity

        Returns:
            Dict of components or None if not found
        """
        # Extract size from variant (e.g., "50m" from "50m / Monument")
        size = None
        if variant:
            parts = variant.split("/")
            if parts:
                size_part = parts[0].strip()
                if "m" in size_part.lower():
                    size = size_part.lower().replace(" ", "")

        # Search for matching product in kit breakdown
        for product in self.kit_breakdown.get("products", []):
            # Match by product name (fuzzy)
            if self._product_matches(title, product["product_name"]):
                # Find matching variant
                for var in product.get("variants", []):
                    var_size = var["size"].lower().replace(" ", "")
                    if size and var_size == size:
                        return var["components"]

                # If no size match, return first variant as default
                if product.get("variants"):
                    return product["variants"][0]["components"]

        return None

    def _product_matches(self, order_title: str, product_name: str) -> bool:
        """Check if an order title matches a product name."""
        order_lower = order_title.lower()
        product_lower = product_name.lower()

        # Check for key terms
        key_terms = ["corrugated", "trimdek", "klip-lok", "tiled", "valley", "box gutter", "ember"]

        for term in key_terms:
            if term in order_lower and term in product_lower:
                return True

        return False

    def get_sync_status(self) -> dict:
        """Get current sync status."""
        return {
            "last_synced": self.cached_orders.get("last_synced"),
            "total_orders": self.cached_orders.get("total_orders", 0),
            "days_fetched": self.cached_orders.get("days_fetched", 0)
        }


# Command-line interface for testing
if __name__ == "__main__":
    sync = ShopifySync()

    print("Shopify Sync CLI")
    print("=" * 40)

    status = sync.get_sync_status()
    print(f"Last synced: {status['last_synced']}")
    print(f"Orders cached: {status['total_orders']}")

    print("\nFetching orders (last 180 days)...")
    orders = sync.fetch_orders(days=180, force_refresh=True)
    print(f"Fetched {len(orders)} orders")

    print("\nCalculating component usage...")
    usage = sync.calculate_component_usage(days=180)
    print(f"Orders analyzed: {usage['order_count']}")
    print(f"Saddles used: {usage['saddles']:,}")
    print(f"Saddle screws: {usage['saddle_screws']:,}")
    print(f"Trim screws: {usage['trim_screws']:,}")
    print(f"Trims: {usage['trims']:,}")
