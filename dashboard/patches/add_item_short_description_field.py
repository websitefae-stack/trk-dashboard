"""
Item.custom_short_description (Data, max 200 chars) - a short blurb
for the online store's listing cards, distinct from the full
description (which can run much longer and was making store cards
unreadable). Falls back to the full description, trimmed, wherever
resilient_domains reads it if a product hasn't been given one yet -
see webshop_items.py's get_store_items().

Safe to run more than once - create_custom_fields skips fields that
already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


ITEM_FIELDS = [
    {
        "fieldname": "custom_short_description",
        "fieldtype": "Data",
        "label": "Short Description (Store card, max 200 chars)",
        "insert_after": "description",
        "length": 200,
        "module": "Dashboard",
    },
]


def execute():
    create_custom_fields({"Item": ITEM_FIELDS}, ignore_validate=True)
    frappe.db.commit()
