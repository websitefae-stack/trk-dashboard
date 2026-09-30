"""
Item.custom_weight / custom_weight_unit - a Store Manager enters a
product's shipping weight in whichever unit is convenient (grams for a
small item, kg for a heavier one) rather than always converting to one
unit by hand. Stored as the raw value + unit exactly as entered (not
pre-converted to grams) so the product form always shows back what was
typed - see store_shipping.py's weight_in_grams() helper, which is the
one place that ever converts this to grams for a shipping calculation.

Left at 0 (the default) for anything that doesn't need posting - a
course, a digital download, a service - so it never contributes to a
cart's shipping weight; see webshop_purchase.py's shipping calculation,
which also independently excludes any item with custom_unlocks_lms_
course or custom_digital_file set regardless of what's typed here.

Safe to run more than once - create_custom_fields skips fields that
already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


ITEM_FIELDS = [
    {
        "fieldname": "custom_weight",
        "fieldtype": "Float",
        "label": "Weight",
        "insert_after": "custom_stock_qty",
        "default": "0",
        "precision": "2",
        "description": "Shipping weight - leave at 0 for a course, digital download, or service that doesn't need posting.",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_weight_unit",
        "fieldtype": "Select",
        "label": "Weight Unit",
        "options": "g\nkg",
        "default": "g",
        "insert_after": "custom_weight",
        "module": "Dashboard",
    },
]


def execute():
    create_custom_fields({"Item": ITEM_FIELDS}, ignore_validate=True)
    frappe.db.commit()
