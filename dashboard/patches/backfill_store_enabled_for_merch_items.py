"""
One-time data cleanup: a lot of Store products (Tote Bag, Sleep Masks,
Fidget Rings, iPad Covers, etc.) were never actually marked
custom_store_enabled=1 - likely created before that field existed, or
added directly in the Desk rather than through store_products.py's own
"Add Product" flow, which always sets it on anything it creates. Without
it, these items look indistinguishable from a real service to both the
Service Access grid (item_access.py) and resilient_domains' coach-profile
pages, which both rely on this exact flag to tell the two apart - so
merch kept leaking onto coach pages as if it were a service they offer.

Can't safely assume "not item_group Services" means "must be
merch" - real services/workshops/packs live in all sorts of item groups
that aren't literally called "Services" (see SERVICE_ITEM_GROUP's own
docstring), not just that one. So this only touches items whose group
is unambiguous: already excluded elsewhere as Courses, or obviously
merch-shaped by name (no reliable positive signal for "service" exists
across the existing data, so this errs toward leaving anything
workshop/coaching-shaped alone rather than risk hiding a real service
again).

Logs exactly which items it touched (frappe.log_error) so this is easy
to audit and, if anything was wrongly caught, quickly reverse by hand.
"""

import frappe

EXCLUDED_GROUPS = {"services", "courses"}
PROTECTED_GROUP_SUBSTRINGS = ("workshop", "coaching")


def execute():
    if not frappe.db.exists("DocType", "Item"):
        return

    item_meta = frappe.get_meta("Item")

    if not item_meta.has_field("custom_store_enabled"):
        return

    rows = frappe.get_all(
        "Item",
        filters={"custom_store_enabled": ["!=", 1]},
        fields=["name", "item_group"],
        limit_page_length=0,
    )

    changed = []

    for row in rows:
        group = (row.get("item_group") or "").strip().lower()

        if not group or group in EXCLUDED_GROUPS:
            continue

        if any(fragment in group for fragment in PROTECTED_GROUP_SUBSTRINGS):
            continue

        frappe.db.set_value("Item", row.name, "custom_store_enabled", 1, update_modified=False)
        changed.append(row.name)

    frappe.db.commit()

    if changed:
        frappe.log_error(
            "backfill_store_enabled_for_merch_items set custom_store_enabled=1 on {0} item(s):\n{1}".format(
                len(changed), "\n".join(changed)
            ),
            "Store Enabled Backfill",
        )
