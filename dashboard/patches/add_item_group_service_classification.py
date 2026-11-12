"""
Sets custom_sells_as (see add_item_group_sells_as_field.py) on every
real Item Group, straight from Ashley's own export/classification -
School, Services, Staff CPD -> Service; Shipping -> Shipping; every
other group (Hoodies, Bags, Coach Merch, Courses, etc.) -> Product.

Originally this only set the 4 non-Product groups explicitly, relying
on the new field's own column default ("Product") to backfill every
pre-existing Item Group row automatically - the same backfill-via-
column-default behaviour already proven elsewhere in this app for a
module-owned doctype's own field (is_active on Coach Onboarding Master
Step). Confirmed live that assumption doesn't reliably hold the same
way for a *custom* field added to a *core* doctype (Item Group isn't
owned by this app) - Ashley saw "Service" still showing against
obviously-Product items (Hoodie variants) after deploying. Rewritten
to explicitly set every group's value rather than leaning on a default
to have backfilled correctly - removes the dependency entirely rather
than trying to figure out exactly why it didn't take.

Safe to re-run - idempotent, and every group gets (re-)set every run,
which also self-heals this exact kind of drift if it ever happens
again for any other reason.
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
