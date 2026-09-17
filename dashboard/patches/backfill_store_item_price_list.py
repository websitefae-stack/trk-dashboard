"""
Same story as backfill_store_item_show_on_site.py, for a second field on
the same row: _ensure_item_default_row() only ever set default_price_list
when it created a brand-new Item Default row - if one already existed
(e.g. adopting a pre-existing, non-store Item into the store - see
create_store_product), its default_price_list was left untouched, which
could point at the wrong price list or none at all.
resilient_domains' get_store_items() looks the price up through this
row's default_price_list rather than the constant directly, so a
mismatch here means it finds no price and the product silently never
shows up in the store listing, with nothing anywhere to explain why.

One-off data fix: forces default_price_list to DEFAULT_PRICE_LIST on
every existing store item's (and its variants', if any) Item Default
row. Safe to run more than once.
"""

import frappe

from dashboard.api.shared.item_access import DEFAULT_PRICE_LIST


def execute():
    if not frappe.db.exists("DocType", "Item Default"):
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
        SET default_price_list = %(price_list)s
        WHERE parent IN %(items)s
          AND (default_price_list IS NULL OR default_price_list != %(price_list)s)
        """,
        {"items": all_item_codes, "price_list": DEFAULT_PRICE_LIST},
    )

    frappe.db.commit()
