"""
Sets custom_sells_as (see add_item_group_sells_as_field.py) on the 4
Item Groups that aren't plain Products, straight from Ashley's own
export/classification - every other Item Group already defaults to
Product via the new field's own column default.

- School, Services, Staff CPD -> Service (every actual service item
  Ashley invoices for lives under one of these three)
- Shipping -> Shipping (the one shipping-fee item, never picked by
  hand onto a service invoice either)

Safe to re-run - only ever sets a value, and does nothing if a group
named here doesn't exist on this site (logged, not thrown, since a
missing group here isn't a reason to fail the whole migrate).
"""

import frappe

SERVICE_ITEM_GROUPS = ["School", "Services", "Staff CPD"]
SHIPPING_ITEM_GROUPS = ["Shipping"]


def execute():
    if not frappe.db.exists("DocType", "Item Group"):
        return

    if not frappe.get_meta("Item Group").has_field("custom_sells_as"):
        return

    missing = []

    for group_name in SERVICE_ITEM_GROUPS:
        if frappe.db.exists("Item Group", group_name):
            frappe.db.set_value("Item Group", group_name, "custom_sells_as", "Service", update_modified=False)
        else:
            missing.append(group_name)

    for group_name in SHIPPING_ITEM_GROUPS:
        if frappe.db.exists("Item Group", group_name):
            frappe.db.set_value("Item Group", group_name, "custom_sells_as", "Shipping", update_modified=False)
        else:
            missing.append(group_name)

    if missing:
        frappe.log_error(
            f"Item Group(s) not found on this site, custom_sells_as not set for: {missing}",
            "Item Group Service Classification - Group(s) Missing",
        )

    frappe.db.commit()
