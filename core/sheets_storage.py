"""
Google Sheets Storage Module

Provides persistent cloud storage for inventory data using Google Sheets.
Falls back to local JSON files if Google Sheets is not configured.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
import streamlit as st

# Try to import gspread, but make it optional for local development
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

# Scopes required for Google Sheets access
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Sheet names for each inventory type
SHEET_NAMES = {
    'screws': 'Screws',
    'trims': 'Trims',
    'saddles': 'Saddles',
    'boxes': 'Boxes',
    'mesh': 'Mesh'
}

# Column headers for each sheet type
SHEET_HEADERS = {
    'screws': ['id', 'screw_type', 'colour', 'quantity', 'source', 'created_at', 'last_updated'],
    'trims': ['id', 'colour', 'quantity', 'source', 'created_at', 'last_updated'],
    'saddles': ['id', 'saddle_type', 'colour', 'quantity', 'source', 'created_at', 'last_updated'],
    'boxes': ['id', 'box_type', 'quantity', 'source', 'created_at', 'last_updated'],
    'mesh': ['id', 'mesh_type', 'width_mm', 'length_m', 'colour', 'quantity', 'received_date', 'location', 'notes', 'created_at']
}


def is_sheets_enabled() -> bool:
    """Check if Google Sheets integration is enabled and configured."""
    if not GSPREAD_AVAILABLE:
        return False

    # Check for credentials in Streamlit secrets or environment
    try:
        if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
            return True
    except Exception:
        pass

    # Check for environment variable with JSON credentials
    if os.getenv('GOOGLE_SHEETS_CREDENTIALS'):
        return True

    return False


def get_credentials():
    """Get Google credentials from Streamlit secrets or environment."""
    # Try Streamlit secrets first (for cloud deployment)
    try:
        if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
            creds_dict = dict(st.secrets['gcp_service_account'])
            return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    except Exception:
        pass

    # Try environment variable (for local development)
    creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
    if creds_json:
        creds_dict = json.loads(creds_json)
        return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

    return None


def get_sheet_id() -> Optional[str]:
    """Get the Google Sheet ID from secrets or environment."""
    # Try Streamlit secrets
    try:
        if hasattr(st, 'secrets') and 'google_sheets' in st.secrets:
            return st.secrets['google_sheets'].get('sheet_id')
    except Exception:
        pass

    # Try environment variable
    return os.getenv('GOOGLE_SHEET_ID')


@st.cache_resource(ttl=300)  # Cache connection for 5 minutes
def get_gspread_client():
    """Get authenticated gspread client."""
    if not GSPREAD_AVAILABLE:
        return None

    creds = get_credentials()
    if not creds:
        return None

    try:
        return gspread.authorize(creds)
    except Exception as e:
        st.warning(f"Could not connect to Google Sheets: {e}")
        return None


def get_worksheet(sheet_type: str):
    """
    Get a worksheet by type (screws, trims, saddles, boxes, mesh).

    Returns None if Google Sheets is not configured.
    """
    client = get_gspread_client()
    if not client:
        return None

    sheet_id = get_sheet_id()
    if not sheet_id:
        return None

    try:
        spreadsheet = client.open_by_key(sheet_id)
        sheet_name = SHEET_NAMES.get(sheet_type, sheet_type.title())

        # Try to get existing worksheet
        try:
            return spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            # Create the worksheet with headers
            worksheet = spreadsheet.add_worksheet(
                title=sheet_name,
                rows=1000,
                cols=len(SHEET_HEADERS.get(sheet_type, []))
            )
            headers = SHEET_HEADERS.get(sheet_type, [])
            if headers:
                worksheet.append_row(headers)
            return worksheet

    except Exception as e:
        st.warning(f"Could not access worksheet '{sheet_type}': {e}")
        return None


def read_inventory(sheet_type: str) -> List[Dict[str, Any]]:
    """
    Read all inventory rows from a sheet.

    Returns list of dictionaries with column headers as keys.
    Returns empty list if Google Sheets is not configured.
    """
    worksheet = get_worksheet(sheet_type)
    if not worksheet:
        return []

    try:
        # Get all records (skips header row automatically)
        records = worksheet.get_all_records()

        # Convert empty strings to appropriate types
        for record in records:
            for key, value in record.items():
                if value == '':
                    record[key] = None
                elif key == 'quantity' and isinstance(value, str):
                    try:
                        record[key] = int(value)
                    except ValueError:
                        record[key] = 0

        return records
    except Exception as e:
        st.warning(f"Error reading from sheet '{sheet_type}': {e}")
        return []


def write_inventory(sheet_type: str, data: List[Dict[str, Any]], append: bool = False) -> bool:
    """
    Write inventory data to a sheet.

    Args:
        sheet_type: Type of inventory (screws, trims, etc.)
        data: List of dictionaries to write
        append: If True, append to existing data. If False, replace all data.

    Returns:
        True if successful, False otherwise.
    """
    worksheet = get_worksheet(sheet_type)
    if not worksheet:
        return False

    try:
        headers = SHEET_HEADERS.get(sheet_type, [])

        if not append:
            # Clear all data except headers
            worksheet.clear()
            if headers:
                worksheet.append_row(headers)

        # Convert data to rows
        rows = []
        for item in data:
            row = []
            for header in headers:
                value = item.get(header, '')
                if value is None:
                    value = ''
                row.append(value)
            rows.append(row)

        # Batch append for efficiency
        if rows:
            worksheet.append_rows(rows)

        return True

    except Exception as e:
        st.error(f"Error writing to sheet '{sheet_type}': {e}")
        return False


def update_row(sheet_type: str, row_id: str, data: Dict[str, Any]) -> bool:
    """
    Update a single row in a sheet by ID.

    Args:
        sheet_type: Type of inventory
        row_id: The ID value to find
        data: Dictionary of fields to update

    Returns:
        True if successful, False otherwise.
    """
    worksheet = get_worksheet(sheet_type)
    if not worksheet:
        return False

    try:
        # Find the row with matching ID
        cell = worksheet.find(row_id, in_column=1)
        if not cell:
            return False

        row_num = cell.row
        headers = SHEET_HEADERS.get(sheet_type, [])

        # Update each field
        for key, value in data.items():
            if key in headers:
                col_num = headers.index(key) + 1
                if value is None:
                    value = ''
                worksheet.update_cell(row_num, col_num, value)

        return True

    except Exception as e:
        st.warning(f"Error updating row in '{sheet_type}': {e}")
        return False


def add_row(sheet_type: str, data: Dict[str, Any]) -> bool:
    """
    Add a single row to a sheet.

    Args:
        sheet_type: Type of inventory
        data: Dictionary representing the row

    Returns:
        True if successful, False otherwise.
    """
    worksheet = get_worksheet(sheet_type)
    if not worksheet:
        return False

    try:
        headers = SHEET_HEADERS.get(sheet_type, [])
        row = []
        for header in headers:
            value = data.get(header, '')
            if value is None:
                value = ''
            row.append(value)

        worksheet.append_row(row)
        return True

    except Exception as e:
        st.warning(f"Error adding row to '{sheet_type}': {e}")
        return False


def delete_row(sheet_type: str, row_id: str) -> bool:
    """
    Delete a row from a sheet by ID.

    Args:
        sheet_type: Type of inventory
        row_id: The ID value to find and delete

    Returns:
        True if successful, False otherwise.
    """
    worksheet = get_worksheet(sheet_type)
    if not worksheet:
        return False

    try:
        cell = worksheet.find(row_id, in_column=1)
        if cell:
            worksheet.delete_rows(cell.row)
            return True
        return False

    except Exception as e:
        st.warning(f"Error deleting row from '{sheet_type}': {e}")
        return False


def clear_cache():
    """Clear the gspread client cache to force reconnection."""
    get_gspread_client.clear()


# Convenience functions for specific inventory types

def read_screws() -> List[Dict[str, Any]]:
    """Read screw inventory from Google Sheets."""
    return read_inventory('screws')


def write_screws(data: List[Dict[str, Any]], append: bool = False) -> bool:
    """Write screw inventory to Google Sheets."""
    return write_inventory('screws', data, append)


def read_trims() -> List[Dict[str, Any]]:
    """Read trim inventory from Google Sheets."""
    return read_inventory('trims')


def write_trims(data: List[Dict[str, Any]], append: bool = False) -> bool:
    """Write trim inventory to Google Sheets."""
    return write_inventory('trims', data, append)


def read_saddles() -> List[Dict[str, Any]]:
    """Read saddle inventory from Google Sheets."""
    return read_inventory('saddles')


def write_saddles(data: List[Dict[str, Any]], append: bool = False) -> bool:
    """Write saddle inventory to Google Sheets."""
    return write_inventory('saddles', data, append)


def read_boxes() -> List[Dict[str, Any]]:
    """Read box inventory from Google Sheets."""
    return read_inventory('boxes')


def write_boxes(data: List[Dict[str, Any]], append: bool = False) -> bool:
    """Write box inventory to Google Sheets."""
    return write_inventory('boxes', data, append)


def read_mesh() -> List[Dict[str, Any]]:
    """Read mesh inventory from Google Sheets."""
    return read_inventory('mesh')


def write_mesh(data: List[Dict[str, Any]], append: bool = False) -> bool:
    """Write mesh inventory to Google Sheets."""
    return write_inventory('mesh', data, append)
