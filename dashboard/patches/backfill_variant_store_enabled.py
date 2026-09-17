"""
Item.custom_store_enabled is meant to be set on every store product AND
each of its variants (see store_products.py's _create_variant_item()) -
but that wasn't always the case: variants created before that function
started setting it on the variant itself (not just its template) were
left with it unset, so they kept slipping past every "exclude store
items" filter that only checks the item's own flag (e.g. the franchisor's
Service Access grid - confirmed live showing store variants that should
never have been there).

Backfills custom_store_enabled=1 onto any variant whose template already
has it set. Safe to run more than once.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Item"):
        return

    item_meta = frappe.get_meta("Item")
    if not item_meta.has_field("custom_store_enabled"):
        return

    store_template_codes = frappe.get_all(
        "Item",
        filters={"custom_store_enabled": 1, "has_variants": 1},
        pluck="name",
    )

    if not store_template_codes:
        return

    stray_variants = frappe.get_all(
        "Item",
        filters={
            "variant_of": ["in", store_template_codes],
            "custom_store_enabled": ["!=", 1],
        },
        pluck="name",
    )

    for item_code in stray_variants:
        frappe.db.set_value("Item", item_code, "custom_store_enabled", 1)

    if stray_variants:
        frappe.db.commit()
