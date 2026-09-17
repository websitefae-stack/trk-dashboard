"""
Every store product created before this fix (see
store_products.py's _ensure_item_default_row) was missing
custom_show_on_site on its Item Default row - the flag
webshop_purchase.py's checkout actually gates a purchase on, separate
from Item.custom_store_enabled (which only controls showing up in a
store listing). Those items list fine on the storefront but refuse to
actually sell with "This item is not available for online purchase."

One-off data fix: backfills custom_show_on_site=1 onto every existing
store item's (and its variants', if any) Item Default row. Safe to run
more than once - only ever sets it, never unsets an existing choice.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Item Default"):
        return

    if not frappe.get_meta("Item Default").has_field("custom_show_on_site"):
        return

    if not frappe.get_meta("Item").has_field("custom_store_enabled"):
        return

    store_item_codes = frappe.get_all("Item", filters={"custom_store_enabled": 1}, pluck="name")

    if not store_item_codes:
        return

    variant_codes = frappe.get_all(
        "Item", filters={"variant_of": ["in", store_item_codes]}, pluck="name"
    )

    all_item_codes = list(set(store_item_codes) | set(variant_codes))

    if not all_item_codes:
        return

    frappe.db.sql(
        """
        UPDATE `tabItem Default`
        SET custom_show_on_site = 1
        WHERE parent IN %(items)s
          AND (custom_show_on_site IS NULL OR custom_show_on_site = 0)
        """,
        {"items": all_item_codes},
    )

    frappe.db.commit()
