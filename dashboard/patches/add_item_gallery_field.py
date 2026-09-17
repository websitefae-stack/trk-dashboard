"""
Item.custom_gallery (Table -> Item Gallery Image) - extra product photos
beyond the single main Item.image, shown as a thumbnail strip on the
public /buy page (resilient_domains). For a variant template, the
gallery shown there also includes every variant's own photo (see
webshop_purchase.py) - this field is what lets a simple (non-variant)
product have more than just the one image too.

Safe to run more than once - create_custom_fields skips fields that
already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


ITEM_FIELDS = [
    {
        "fieldname": "custom_gallery",
        "fieldtype": "Table",
        "options": "Item Gallery Image",
        "label": "Additional Photos",
        "insert_after": "image",
        "module": "Dashboard",
    },
]


def execute():
    create_custom_fields({"Item": ITEM_FIELDS}, ignore_validate=True)
    frappe.db.commit()
