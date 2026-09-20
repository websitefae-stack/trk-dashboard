"""
Coach-only store items + fixed coach pricing:

- Item.custom_item_visibility (Select: "Everyone"/"Coach Only") - set on
  the Add/Edit Product form in the Store dashboard (see store_products.py),
  read on the storefront side by resilient_domains' get_purchasable_item/
  get_store_items and enforced again server-side at checkout by
  dashboard.api.shared.webshop_purchase's _get_purchasable_item. Blank
  (every existing item, before this patch) is treated as "Everyone"
  everywhere it's read - no backfill needed. A variant copies its
  template's visibility at creation time, same as the brand fields.

- The "Coach Only Price List" Price List record itself (see item_access.
  COACH_ONLY_PRICE_LIST) - an Item Price can't reference a Price List
  that doesn't exist yet, so this has to be created before
  store_products.py's _set_item_price() is ever called against it.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ITEM_FIELDS = [
    {
        "fieldname": "custom_item_visibility",
        "fieldtype": "Select",
        "length": 20,
        "label": "Store Visibility",
        "options": "Everyone\nCoach Only",
        "description": "\"Coach Only\" hides this item from the public store entirely - it only ever shows to a logged-in coach, in the Coach Store.",
        "insert_after": "custom_store_enabled",
        "module": "Dashboard",
    },
]


def execute():
    if frappe.db.exists("DocType", "Item"):
        create_custom_fields({"Item": ITEM_FIELDS}, ignore_validate=True)

    if frappe.db.exists("DocType", "Price List") and not frappe.db.exists("Price List", "Coach Only Price List"):
        frappe.get_doc({
            "doctype": "Price List",
            "price_list_name": "Coach Only Price List",
            "selling": 1,
            "currency": "GBP",
            "enabled": 1,
        }).insert(ignore_permissions=True)

    frappe.db.commit()
