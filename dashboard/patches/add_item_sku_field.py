"""
Item.custom_sku (Data) - a separate, store-manager-assigned SKU/product
code distinct from Item.item_code (which is the item's own internal name,
e.g. "Fidget Rings" or "Fidget Rings-8-MNS" for a variant) - lets a
Coach/Store Manager use their own numbering scheme, shown on the Orders
list/detail so a packed order can be matched against physical stock.

Safe to run more than once - create_custom_fields skips fields that
already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


ITEM_FIELDS = [
    {
        "fieldname": "custom_sku",
        "fieldtype": "Data",
        "label": "SKU",
        "insert_after": "item_code",
        "module": "Dashboard",
    },
]


def execute():
    create_custom_fields({"Item": ITEM_FIELDS}, ignore_validate=True)
    frappe.db.commit()
