"""
Stocktake Wizard Page
A step-by-step wizard for entering inventory counts.
Supports 7 categories with auto-push to inventory on section completion.
"""

import streamlit as st
import sys
import os

# Add parent directories to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from stocktake_wizard.item_generator import generate_all_items, get_category_counts, CATEGORY_NAMES
from stocktake_wizard.wizard_state import WizardState
from stocktake_wizard.inventory_updater import apply_category_stocktake

# Custom CSS for clean appearance
st.markdown("""
<style>
    /* Main container styling */
    .main .block-container {
        max-width: 700px;
        padding-top: 2rem;
    }

    /* Category header */
    .category-header {
        background: #1A365D;
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 8px 8px 0 0;
        margin-bottom: 0;
    }

    /* Progress text */
    .progress-text {
        color: #EBF0F8;
        font-size: 0.9rem;
    }

    /* Item card */
    .item-card {
        background: #f8f9fa;
        border: 2px solid #1A365D;
        border-top: none;
        border-radius: 0 0 8px 8px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }

    /* Type name */
    .type-name {
        font-size: 1.5rem;
        font-weight: 600;
        color: #1A365D;
        margin-bottom: 0.5rem;
    }

    /* Colour display */
    .colour-display {
        font-size: 1.2rem;
        color: #41424C;
        margin-bottom: 1rem;
    }

    /* Dimensions */
    .dimensions {
        font-size: 1rem;
        color: #666;
        margin-bottom: 1rem;
    }

    /* Input section */
    .input-section {
        background: white;
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 1rem;
    }

    /* Button styling */
    .stButton > button {
        width: 100%;
    }

    /* Success box */
    .success-box {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }

    /* Category card */
    .category-card {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.5rem;
    }

    .category-card.completed {
        background: #d4edda;
        border-color: #c3e6cb;
    }

    .category-card.in-progress {
        background: #fff3cd;
        border-color: #ffc107;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if 'wizard_state' not in st.session_state:
        st.session_state.wizard_state = None
    if 'screen' not in st.session_state:
        st.session_state.screen = 'welcome'
    if 'selected_categories' not in st.session_state:
        st.session_state.selected_categories = []
    if 'completed_categories' not in st.session_state:
        st.session_state.completed_categories = set()
    if 'pushed_categories' not in st.session_state:
        st.session_state.pushed_categories = set()
    if 'current_category' not in st.session_state:
        st.session_state.current_category = None
    if 'push_results' not in st.session_state:
        st.session_state.push_results = {}


def render_welcome_screen():
    """Render the welcome/start screen."""
    st.title("Stocktake Wizard")
    st.markdown("### Gutter Guard Warehouse")

    st.markdown("---")

    # Check for saved progress
    saved_info = WizardState.get_saved_progress_info()
    if saved_info:
        st.warning("**Saved progress found!**")
        st.markdown(f"""
        - Started: {saved_info['started_at'][:10] if saved_info['started_at'] else 'Unknown'}
        - Progress: {saved_info['completed']} / {saved_info['total']} items
        - Categories: {', '.join(CATEGORY_NAMES.get(c, c) for c in saved_info['categories'])}
        """)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Resume Stocktake", type="primary", use_container_width=True):
                st.session_state.wizard_state = WizardState.load_progress()
                st.session_state.selected_categories = saved_info['categories']
                st.session_state.screen = 'category_select'
                st.rerun()
        with col2:
            if st.button("Start Fresh", use_container_width=True):
                WizardState.clear_progress()
                st.session_state.completed_categories = set()
                st.session_state.pushed_categories = set()
                st.session_state.screen = 'categories'
                st.rerun()
    else:
        st.markdown("""
        This wizard guides you through counting inventory by category.
        Select which categories to count, then enter quantities one item at a time.

        **Auto-push:** When you complete all items in a category, it will automatically
        update the inventory.

        **Categories available:**
        """)

        counts = get_category_counts()
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Screws", f"{counts['screws']} items")
            st.metric("Trims", f"{counts['trims']} items")
            st.metric("Corrugated Saddles", f"{counts['corrugated_saddles']} items")
            st.metric("Trimdek Saddles", f"{counts['trimdek_saddles']} items")
        with col2:
            st.metric("Boxes", f"{counts['boxes']} items")
            st.metric("4mm Mesh", f"{counts['mesh_4mm']} items")
            st.metric("2mm Ember Mesh", f"{counts['mesh_2mm']} items")

        st.metric("**Total**", f"{sum(counts.values())} items")

        st.markdown("---")

        if st.button("Start Stocktake", type="primary", use_container_width=True):
            st.session_state.screen = 'categories'
            st.rerun()


@st.dialog("Confirm Stocktake")
def confirm_stocktake_dialog():
    """Show confirmation dialog before starting stocktake."""
    st.warning("**Warning:** This stocktake will replace all existing stock levels for the selected categories.")
    st.markdown("Any current inventory data will be overwritten with the new counts you enter.")
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("I Understand, Continue", type="primary", use_container_width=True):
            st.session_state.confirmed_stocktake = True
            st.rerun()


def render_category_selection():
    """Render category selection screen."""
    st.title("Select Categories")
    st.markdown("Choose which categories to count in this stocktake.")

    st.markdown("---")

    counts = get_category_counts()

    categories = []

    # Create checkboxes for each category
    col1, col2 = st.columns(2)

    with col1:
        if st.checkbox(f"Screws ({counts['screws']} items)", value=True):
            categories.append('screws')
        if st.checkbox(f"Trims ({counts['trims']} items)", value=True):
            categories.append('trims')
        if st.checkbox(f"Corrugated Saddles ({counts['corrugated_saddles']} items)", value=True):
            categories.append('corrugated_saddles')
        if st.checkbox(f"Trimdek Saddles ({counts['trimdek_saddles']} items)", value=True):
            categories.append('trimdek_saddles')

    with col2:
        if st.checkbox(f"Boxes ({counts['boxes']} items)", value=True):
            categories.append('boxes')
        if st.checkbox(f"4mm Mesh ({counts['mesh_4mm']} items)", value=True):
            categories.append('mesh_4mm')
        if st.checkbox(f"2mm Ember Mesh ({counts['mesh_2mm']} items)", value=True):
            categories.append('mesh_2mm')

    # Calculate total
    total = sum(counts[c] for c in categories) if categories else 0
    st.markdown(f"**Selected: {len(categories)} categories, {total} items**")

    st.markdown("---")

    # Check if user confirmed the stocktake
    if st.session_state.get('confirmed_stocktake') and st.session_state.get('pending_categories'):
        # User confirmed - proceed with stocktake
        categories_to_use = st.session_state.pending_categories
        items = generate_all_items(categories_to_use)
        state = WizardState()
        state.initialize(items, categories_to_use)
        st.session_state.wizard_state = state
        st.session_state.selected_categories = categories_to_use
        st.session_state.completed_categories = set()
        st.session_state.pushed_categories = set()
        st.session_state.confirmed_stocktake = False
        st.session_state.pending_categories = None
        st.session_state.screen = 'category_select'
        st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back", use_container_width=True):
            st.session_state.screen = 'welcome'
            st.rerun()
    with col2:
        if st.button("Begin Counting", type="primary", use_container_width=True, disabled=not categories):
            # Store categories and show confirmation dialog
            st.session_state.pending_categories = categories
            confirm_stocktake_dialog()


def render_category_select_screen():
    """Render category selection screen for manual changes."""
    st.title("Select Category")
    st.markdown("Choose a category to count or update.")

    state: WizardState = st.session_state.wizard_state

    if not state:
        st.session_state.screen = 'welcome'
        st.rerun()
        return

    st.markdown("---")

    counts = get_category_counts()
    cat_progress = state.get_category_progress()

    # Show each category with its progress
    for cat in st.session_state.selected_categories:
        cat_name = CATEGORY_NAMES.get(cat, cat)
        info = cat_progress.get(cat, {"completed": 0, "total": counts.get(cat, 0)})

        is_complete = info['completed'] == info['total'] and info['total'] > 0
        is_pushed = cat in st.session_state.pushed_categories

        # Status indicator
        if is_pushed:
            status = "Pushed to inventory"
        elif is_complete:
            status = "Ready to push"
        elif info['completed'] > 0:
            status = f"{info['completed']}/{info['total']} entered"
        else:
            status = "Not started"

        # Category card
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{cat_name}** - {info['total']} items")
            st.caption(status)
        with col2:
            if is_pushed:
                st.button("Done", key=f"btn_{cat}", disabled=True, use_container_width=True)
            else:
                if st.button("Count" if not is_complete else "Review",
                             key=f"btn_{cat}", use_container_width=True):
                    st.session_state.current_category = cat
                    st.session_state.screen = 'entry'
                    st.rerun()

        # Show item review list if complete (before push button)
        if is_complete and not is_pushed:
            # Get entries for this category
            summary = state.get_summary()
            cat_entries = [e for e in summary if e['category'] == cat]

            with st.expander(f"Review {len(cat_entries)} items", expanded=True):
                non_zero = [e for e in cat_entries if (e.get('quantity') or 0) > 0]
                zero_count = len(cat_entries) - len(non_zero)

                if non_zero:
                    for entry in non_zero:
                        qty = entry.get('quantity', 0)
                        if cat == 'screws':
                            st.markdown(f"- **{entry['colour']}**: {qty:,} screws")
                        elif cat == 'trims':
                            st.markdown(f"- **{entry['colour']}**: {qty} trims")
                        elif cat in ['corrugated_saddles', 'trimdek_saddles']:
                            st.markdown(f"- **{entry['colour']}**: {qty} saddles")
                        elif cat == 'boxes':
                            st.markdown(f"- **{entry['type_name']}**: {qty} boxes")
                        elif cat in ['mesh_4mm', 'mesh_2mm']:
                            st.markdown(f"- **{entry['colour']}** {entry['width_mm']}mm x {entry['length_m']}m: {qty} rolls")
                        else:
                            st.markdown(f"- **{entry.get('colour', 'Item')}**: {qty}")

                if zero_count > 0:
                    st.caption(f"*{zero_count} items with zero stock not shown*")

                if not non_zero:
                    st.caption("*All items have zero stock*")

        # Show push button if complete but not pushed
        if is_complete and not is_pushed:
            if st.button(f"Push {cat_name} to Inventory", key=f"push_{cat}",
                         type="primary", use_container_width=True):
                # Get entries for this category
                summary = state.get_summary()
                cat_entries = [e for e in summary if e['category'] == cat]

                # Set None quantities to 0
                for entry in cat_entries:
                    if entry.get('quantity') is None:
                        entry['quantity'] = 0

                # Apply stocktake for this category
                with st.spinner(f"Updating {cat_name} inventory..."):
                    result = apply_category_stocktake(cat_entries, cat)

                st.session_state.pushed_categories.add(cat)
                st.session_state.push_results[cat] = result
                st.success(f"{cat_name} inventory updated!")
                st.rerun()

        st.markdown("---")

    # Overall progress
    total_cats = len(st.session_state.selected_categories)
    pushed_cats = len(st.session_state.pushed_categories)
    st.markdown(f"**Overall Progress:** {pushed_cats}/{total_cats} categories pushed")

    # All done?
    if pushed_cats == total_cats:
        st.success("All categories have been pushed to inventory!")
        st.balloons()

        if st.button("Start New Stocktake", type="primary", use_container_width=True):
            WizardState.clear_progress()
            st.session_state.wizard_state = None
            st.session_state.screen = 'welcome'
            st.session_state.completed_categories = set()
            st.session_state.pushed_categories = set()
            st.session_state.push_results = {}
            st.rerun()

    # Save progress button
    st.markdown("---")
    if st.button("Save Progress", use_container_width=True):
        state.save_progress()
        st.success("Progress saved!")


def render_entry_screen():
    """Render the item entry screen."""
    state: WizardState = st.session_state.wizard_state
    current_cat = st.session_state.current_category

    if not state or not current_cat:
        st.session_state.screen = 'category_select'
        st.rerun()
        return

    # Get items for this category
    all_items = state.items
    cat_items = [item for item in all_items if item['category'] == current_cat]

    # Find current item in this category
    cat_progress = state.get_category_progress()

    # Find first incomplete item in this category, or start from beginning
    current_cat_index = 0
    for i, item in enumerate(cat_items):
        if state.get_quantity(item['id']) is None:
            current_cat_index = i
            break
    else:
        # All items complete, start from beginning for review
        current_cat_index = 0

    # Track current item within category
    if 'cat_item_index' not in st.session_state or st.session_state.get('last_cat') != current_cat:
        st.session_state.cat_item_index = current_cat_index
        st.session_state.last_cat = current_cat

    cat_index = st.session_state.cat_item_index

    if cat_index >= len(cat_items):
        cat_index = len(cat_items) - 1
        st.session_state.cat_item_index = cat_index

    item = cat_items[cat_index] if cat_items else None

    if not item:
        st.session_state.screen = 'category_select'
        st.rerun()
        return

    # Count completed items in this category
    completed_in_cat = sum(1 for i in cat_items if state.get_quantity(i['id']) is not None)

    # Category header with progress
    cat_name = CATEGORY_NAMES.get(current_cat, current_cat.upper())

    st.markdown(f"""
    <div class="category-header">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 1.2rem; font-weight: 600;">{cat_name}</span>
            <span class="progress-text">{cat_index + 1} / {len(cat_items)}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Progress bar
    st.progress((cat_index + 1) / len(cat_items))

    st.caption(f"{completed_in_cat}/{len(cat_items)} items entered")

    # Item details card
    st.markdown("---")

    # Display based on category
    if current_cat == 'screws':
        st.markdown(f"### {item['type_name']}")
        st.markdown(f"**Colour:** {item['colour']}")

        st.markdown("---")
        st.markdown("#### How many in stock?")

        current_qty = state.get_quantity(item['id'])
        default_val = current_qty if current_qty is not None else 0

        input_mode = st.radio(
            "Enter as:",
            ["Individual screws", "Boxes (x1000)"],
            horizontal=True,
            label_visibility="collapsed"
        )

        if input_mode == "Boxes (x1000)":
            boxes = st.number_input(
                "Number of boxes",
                min_value=0,
                value=default_val // 1000 if default_val else 0,
                step=1,
                key=f"boxes_{item['id']}"
            )
            quantity = boxes * 1000
            st.caption(f"= {quantity:,} screws")
        else:
            quantity = st.number_input(
                "Number of screws",
                min_value=0,
                value=default_val,
                step=100,
                key=f"qty_{item['id']}"
            )

    elif current_cat == 'trims':
        st.markdown(f"### {item['type_name']}")
        st.markdown(f"**Colour:** {item['colour']}")

        st.markdown("---")
        st.markdown("#### How many trims in stock?")

        current_qty = state.get_quantity(item['id'])
        default_val = current_qty if current_qty is not None else 0

        quantity = st.number_input(
            "Number of trims",
            min_value=0,
            value=default_val,
            step=1,
            key=f"qty_{item['id']}"
        )

    elif current_cat in ['corrugated_saddles', 'trimdek_saddles']:
        st.markdown(f"### {item['type_name']}")
        st.markdown(f"**Colour:** {item['colour']}")

        st.markdown("---")
        st.markdown("#### How many saddles in stock?")

        current_qty = state.get_quantity(item['id'])
        default_val = current_qty if current_qty is not None else 0

        quantity = st.number_input(
            "Number of saddles",
            min_value=0,
            value=default_val,
            step=10,
            key=f"qty_{item['id']}"
        )

    elif current_cat == 'boxes':
        st.markdown(f"### {item['type_name']}")
        st.markdown(f"*{item.get('description', '')}*")

        st.markdown("---")
        st.markdown("#### How many in stock?")

        current_qty = state.get_quantity(item['id'])
        default_val = current_qty if current_qty is not None else 0

        pack_size = item.get('pack_size', 1)
        input_mode = st.radio(
            "Enter as:",
            ["Individual boxes", f"Packs (x{pack_size})"],
            horizontal=True,
            label_visibility="collapsed"
        )

        if "Packs" in input_mode:
            packs = st.number_input(
                "Number of packs",
                min_value=0,
                value=default_val // pack_size if default_val else 0,
                step=1,
                key=f"packs_{item['id']}"
            )
            quantity = packs * pack_size
            st.caption(f"= {quantity:,} boxes")
        else:
            quantity = st.number_input(
                "Number of boxes",
                min_value=0,
                value=default_val,
                step=1,
                key=f"qty_{item['id']}"
            )

    elif current_cat in ['mesh_4mm', 'mesh_2mm']:
        st.markdown(f"### {item['type_name']}")
        st.markdown(f"**Colour:** {item['colour']}")
        st.markdown(f"**Size:** {item['width_mm']}mm x {item['length_m']}m")

        st.markdown("---")
        st.markdown("#### How many rolls in stock?")

        current_qty = state.get_quantity(item['id'])
        default_val = current_qty if current_qty is not None else 0

        quantity = st.number_input(
            "Number of rolls",
            min_value=0,
            value=default_val,
            step=1,
            key=f"qty_{item['id']}"
        )

    else:
        # Fallback for any other category
        st.markdown(f"### {item.get('type_name', 'Item')}")
        if item.get('colour'):
            st.markdown(f"**Colour:** {item['colour']}")

        current_qty = state.get_quantity(item['id'])
        default_val = current_qty if current_qty is not None else 0

        quantity = st.number_input(
            f"Quantity ({item.get('unit', 'units')})",
            min_value=0,
            value=default_val,
            step=1,
            key=f"qty_{item['id']}"
        )

    st.markdown("---")

    # Navigation buttons
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if cat_index > 0:
            if st.button("Previous", use_container_width=True):
                st.session_state.cat_item_index -= 1
                st.rerun()

    with col2:
        if st.button("Skip (0)", use_container_width=True):
            state.set_quantity(item['id'], 0)
            if cat_index < len(cat_items) - 1:
                st.session_state.cat_item_index += 1
            else:
                # Last item - check if category is complete
                check_category_complete(state, current_cat, cat_items)
            st.rerun()

    with col3:
        if st.button("Next", type="primary", use_container_width=True):
            state.set_quantity(item['id'], quantity)
            if cat_index < len(cat_items) - 1:
                st.session_state.cat_item_index += 1
            else:
                # Last item - check if category is complete
                check_category_complete(state, current_cat, cat_items)
            st.rerun()

    # Bottom navigation
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back to Categories", use_container_width=True):
            st.session_state.screen = 'category_select'
            st.rerun()
    with col2:
        if st.button("Save Progress", use_container_width=True):
            state.save_progress()
            st.success("Progress saved!")


def check_category_complete(state: WizardState, category: str, cat_items: list):
    """Check if a category is complete and trigger auto-push."""
    completed = all(state.get_quantity(item['id']) is not None for item in cat_items)

    if completed:
        st.session_state.completed_categories.add(category)
        # Go back to category select for auto-push
        st.session_state.screen = 'category_select'


# Main entry point
init_session_state()

# Route to appropriate screen
screen = st.session_state.screen

if screen == 'welcome':
    render_welcome_screen()
elif screen == 'categories':
    render_category_selection()
elif screen == 'category_select':
    render_category_select_screen()
elif screen == 'entry':
    render_entry_screen()
else:
    st.session_state.screen = 'welcome'
    st.rerun()
