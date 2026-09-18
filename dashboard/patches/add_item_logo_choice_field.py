"""
Item.custom_logo_choice_enabled - some store products (the hoodies and
leggings) let the buyer pick which of the four brand logos (The
Resilient Kid/Teen/People/School) goes on the sleeve or leg, without
that being a real variant of its own (it doesn't affect price/stock,
just which logo gets printed) - see store_products.py and the new
Store Logo Choice single doctype (add_store_logo_choice_doctype.py)
that holds the four logo images shown to pick from.

Safe to run more than once - create_custom_fields skips fields that
already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


ITEM_FIELDS = [
    {
        "fieldname": "custom_logo_choice_enabled",
        "fieldtype": "Check",
        "label": "Let Buyer Choose a Sleeve/Leg Logo",
        "description": "Shows the four brand logos (Kid/Teen/People/School) on the product page - the buyer must pick one before adding to cart, so fulfilment knows which logo to print.",
        "insert_after": "custom_personalization_label",
        "module": "Dashboard",
    },
]


def execute():
    create_custom_fields({"Item": ITEM_FIELDS}, ignore_validate=True)
    frappe.db.commit()
