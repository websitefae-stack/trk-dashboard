"""
Adds "Sells As" (Product/Service/Shipping) to Item Group - the real
classification Ashley's been asking for repeatedly so the invoice item
picker shows her only Services, not every Store product too.

The previous attempt at this (see get_link_options' Item branch in
invoices.py, and backfill_store_enabled_for_merch_items.py /
correct_store_enabled_using_item_visibility.py before it) relied on
custom_store_enabled - a Store *visibility* flag, not a product/service
classification, and it kept mis-firing (a real service like CPD
Training under "Staff CPD" got mistaken for a store product once
already, per correct_store_enabled_using_item_visibility.py's own
history). Ashley settled this properly herself: she exported every
Item, classified each one's Item Group (not each item individually) as
Product/Service/Shipping, and confirmed none of the 29 real item groups
in use mix classifications - every item in a given group is always the
same one of the three. Classifying at the Item Group level, not the
Item level, means a brand new product added under an existing group
never needs separate tagging.

default "Product" so every existing Item Group (and anything not
explicitly set below) backfills to Product - the safe default, since
the actual problem was products leaking in, not services being hidden.
See add_item_group_service_classification.py for the 4 groups that
actually need overriding (Service: School/Services/Staff CPD;
Shipping: Shipping).
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ITEM_GROUP_FIELDS = [
    {
        "fieldname": "custom_sells_as",
        "fieldtype": "Select",
        "label": "Sells As",
        "options": "Product\nService\nShipping",
        "default": "Product",
        "insert_after": "item_group_name",
        "module": "Dashboard",
        "description": (
            "Every Item under this group is one of these - used to show Ashley/coaches only "
            "Services when raising an invoice, and to keep Store/Shipping items out of that list."
        ),
    },
]


def execute():
    if not frappe.db.exists("DocType", "Item Group"):
        return

    create_custom_fields({"Item Group": ITEM_GROUP_FIELDS}, ignore_validate=True)
    frappe.db.commit()
