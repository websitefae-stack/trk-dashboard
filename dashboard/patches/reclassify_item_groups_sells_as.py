"""
Re-does what add_item_group_service_classification.py was meant to do,
under a new patch name so it actually runs again - Frappe never re-runs
a patch it's already logged as executed, even after the file's content
changes (same reason podcast imports etc. have needed a "v2"/re-fire
patch before in this app).

Ashley confirmed live that leaning on custom_sells_as's own column
default ("Product") to backfill every pre-existing Item Group - the
original patch only explicitly set the 4 non-Product groups - didn't
reliably take for a *custom* field added to a *core* doctype the way
it does for a real field on a doctype this app owns: Hoodie variants
(item group "Hoodies, Adult, Kids, Teens, Oxytocin") were still showing
Service after that patch had already run. This one explicitly sets
every Item Group's value outright instead, Product included - nothing
here depends on a default having applied correctly.

Safe to re-run.
"""

import frappe

SERVICE_ITEM_GROUPS = ["School", "Services", "Staff CPD"]
SHIPPING_ITEM_GROUPS = ["Shipping"]


def execute():
    if not frappe.db.exists("DocType", "Item Group"):
        return

    if not frappe.get_meta("Item Group").has_field("custom_sells_as"):
        return

    all_groups = frappe.get_all("Item Group", pluck="name")

    for group_name in all_groups:
        if group_name in SERVICE_ITEM_GROUPS:
            value = "Service"
        elif group_name in SHIPPING_ITEM_GROUPS:
            value = "Shipping"
        else:
            value = "Product"

        frappe.db.set_value("Item Group", group_name, "custom_sells_as", value, update_modified=False)

    missing = [
        group_name
        for group_name in SERVICE_ITEM_GROUPS + SHIPPING_ITEM_GROUPS
        if group_name not in all_groups
    ]
    if missing:
        frappe.log_error(
            f"Item Group(s) not found on this site, custom_sells_as not set for: {missing}",
            "Item Group Service Classification - Group(s) Missing",
        )

    frappe.db.commit()
