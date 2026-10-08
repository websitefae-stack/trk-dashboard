"""
Store products never had any per-coach access gating before now (see
item_access.get_item_access_grid, which used to exclude them entirely -
"always sold by office/HQ... never per-coach") - get_coach_store_items
in resilient_domains showed every custom_store_enabled item to every
coach unconditionally. Ashley wants the same manual-access model
services already use to also apply to products, but NOT retroactively:
every product already live and visible today should stay visible to
every coach it's visible to now - only a brand-new product from this
point forward should start with zero access, requiring a deliberate
grant on the Item Access page (same as a new service already does).

Grants Access + Show on Site to every coach-with-a-company, for every
existing store product template (not variants - access is granted at
the template level, see get_item_access_grid's own docstring), using
the exact same core grant function the "Give access to all coaches"
button itself calls - so this is indistinguishable from Ashley having
clicked that button once for every product that existed before this
patch ran.

Safe to re-run: _grant_item_access_to_all_coaches_unchecked already
no-ops for a coach who already has an Item Default row for that item.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Item"):
        return

    item_meta = frappe.get_meta("Item")
    if not item_meta.has_field("custom_store_enabled"):
        return

    from dashboard.api.shared.item_access import _grant_item_access_to_all_coaches_unchecked

    product_codes = frappe.get_all(
        "Item",
        filters={"custom_store_enabled": 1, "variant_of": ["is", "not set"]},
        pluck="name",
    )

    for item_code in product_codes:
        try:
            _grant_item_access_to_all_coaches_unchecked(item_code, show_on_site=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Backfill Item Access For Store Product Failed - {item_code}")

    frappe.db.commit()
