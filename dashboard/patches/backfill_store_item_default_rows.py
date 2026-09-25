"""
The two older backfills (backfill_store_item_show_on_site.py,
backfill_store_item_price_list.py) only ever repair an EXISTING Item
Default row - a plain UPDATE ... WHERE parent IN (...), a no-op for any
store item with no Item Default row for the webshop company at all.
That row is only ever created from scratch by the guided Store
dashboard product form (_ensure_item_default_row) - an Item created or
edited directly in Desk (e.g. a variant added by hand) can end up with
custom_store_enabled ticked but no Item Default row whatsoever, which
means it silently never appears in either store listing, with nothing
anywhere to explain why. See store_products.py's new
auto_setup_store_item_for_webshop (Item.on_update hook) for the same
fix applied automatically going forward, and its
backfill_store_item_default_rows() for the same one-off fix, re-runnable
any time by a franchisor/Store Manager without needing another deploy.

One-off data fix: runs _sync_item_default_row_raw() (creates the row
if missing, repairs it if not) against every existing store item and
its variants. Safe to run more than once.
"""

import frappe

from dashboard.api.shared.store_products import _backfill_store_item_default_rows


def execute():
    if not frappe.db.exists("DocType", "Item"):
        return

    _backfill_store_item_default_rows()
