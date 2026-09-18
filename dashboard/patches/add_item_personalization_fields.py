"""
Item.custom_personalization_enabled / custom_personalization_label - a
handful of store products can be personalised (e.g. a name printed on
a laptop case) - see store_products.py. The label is what's shown to
the customer above the text box (e.g. "Add the name to be printed"),
falling back to a generic "Personalization" wherever it's left blank.

Safe to run more than once - create_custom_fields skips fields that
already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


ITEM_FIELDS = [
    {
        "fieldname": "custom_personalization_enabled",
        "fieldtype": "Check",
        "label": "Allow Personalization",
        "description": "Shows a free-text box on the product page for the customer to fill in (e.g. a name to print) - optional for them to fill in.",
        "insert_after": "custom_sku",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_personalization_label",
        "fieldtype": "Data",
        "label": "Personalization Label",
        "description": "Shown to the customer above the text box, e.g. \"Name to be printed\". Leave blank to use a generic label.",
        "insert_after": "custom_personalization_enabled",
        "depends_on": "eval:doc.custom_personalization_enabled",
        "module": "Dashboard",
    },
]


def execute():
    create_custom_fields({"Item": ITEM_FIELDS}, ignore_validate=True)
    frappe.db.commit()
