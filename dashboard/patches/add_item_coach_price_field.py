"""
A variant template (Item.has_variants=1) can never have its own Item
Price row - core Frappe rejects it outright ("Item Price cannot be
created for the template item"), which is exactly the 417 Rachel hit
saving a Coach Price on a hoodie with sizes. So a template's one flat
Coach Price (same rate for every size/colour - see store_products.py's
_set_coach_price/_get_coach_price) lives in this plain custom field on
Item instead, read directly (not via Item Price) whenever the item
being coach-priced turns out to be a template.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ITEM_FIELDS = [
    {
        "fieldname": "custom_coach_price",
        "fieldtype": "Currency",
        "label": "Coach Price (variant template only)",
        "description": "One flat Coach Price for every size/variant of this product - only used when this Item has variations (a plain product's Coach Price still uses the normal Item Price mechanism).",
        "insert_after": "custom_item_visibility",
        "module": "Dashboard",
    },
]


def execute():
    if frappe.db.exists("DocType", "Item"):
        create_custom_fields({"Item": ITEM_FIELDS}, ignore_validate=True)

    frappe.db.commit()
