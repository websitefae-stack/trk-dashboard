"""
Adds custom_delivery_method to Sales Invoice - lets a Coach Store order
record whether the coach chose to collect it in person or have it
shipped (see create_coach_store_order in webshop_purchase.py, which
only charges the normal shipping fee - calculate_shipping_amount, same
as the public store checkout - when "Shipping" is chosen). Defaults to
"Collection" so an invoice raised before this field existed, or any
other Sales Invoice never offered the choice, reads as the no-charge
option rather than blank.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

SALES_INVOICE_FIELDS = [
    {
        "fieldname": "custom_delivery_method",
        "fieldtype": "Select",
        "label": "Delivery Method",
        "options": "Collection\nShipping",
        "default": "Collection",
        "insert_after": "customer",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Sales Invoice"):
        return

    create_custom_fields({"Sales Invoice": SALES_INVOICE_FIELDS}, ignore_validate=True)
    frappe.db.commit()
