"""
Keeps a store product's custom_stock_qty honest against every Sales
Invoice it's actually sold on - whether that invoice came from the
online checkout (webshop_purchase.py's create_checkout_session/
stripe_webhook flow) or was raised by hand, e.g. invoicing a coach for
merch directly from Selling > Sales Invoice. Both paths submit/cancel
the exact same core Sales Invoice doctype, so one pair of hooks here
(wired in hooks.py's doc_events) covers both rather than duplicating
this in webshop_purchase.py as well.

Only ever adjusts custom_stock_qty for an Item that is
custom_store_enabled and not custom_unlimited_stock - every other
invoice line (coaching sessions, packages, anything not managed
through the Store dashboard) is left untouched.
"""

import frappe


def _adjustable_store_item_codes(invoice):
    item_meta = frappe.get_meta("Item")

    if not item_meta.has_field("custom_store_enabled") or not item_meta.has_field("custom_stock_qty"):
        return set()

    item_codes = {row.item_code for row in (invoice.items or []) if row.item_code}
    if not item_codes:
        return set()

    rows = frappe.get_all(
        "Item",
        filters={
            "name": ["in", list(item_codes)],
            "custom_store_enabled": 1,
            "custom_unlimited_stock": 0,
        },
        fields=["name"],
    )
    return {row.name for row in rows}


def _adjust_stock(invoice, direction):
    """direction=-1 on submit (sold), +1 on cancel (given back)."""
    adjustable = _adjustable_store_item_codes(invoice)
    if not adjustable:
        return

    for row in invoice.items or []:
        if row.item_code not in adjustable:
            continue

        qty = int(row.qty or 0)
        if not qty:
            continue

        current = frappe.db.get_value("Item", row.item_code, "custom_stock_qty") or 0
        new_qty = current + (direction * qty)

        if new_qty < 0:
            # Sold more than was on record as in stock (e.g. an online
            # sale and a manual invoice both went through before either
            # updated the count) - surfaces as a discoverable log rather
            # than a confusing negative number on the Store dashboard.
            frappe.log_error(
                f"Store item {row.item_code} oversold on {invoice.name}: "
                f"{current} in stock, {qty} sold. Clamped to 0.",
                "Store Stock Oversold",
            )
            new_qty = 0

        frappe.db.set_value("Item", row.item_code, "custom_stock_qty", new_qty)


def decrement_stock_on_submit(doc, method=None):
    _adjust_stock(doc, -1)


def restore_stock_on_cancel(doc, method=None):
    _adjust_stock(doc, 1)
