"""
Adds the fields behind the new online store (distinct from the existing
per-coach "Show on Site" / Item Access feature in add_item_show_on_site_
and_brand_fields.py, which is about a specific coach's own public profile
listing a service they offer):

- Item.custom_store_enabled (Check) - list this item in the general
  online store at all. The existing custom_brand_hub/_kid/_teen/_people/
  _school fields (already on Item) are reused as-is to control which of
  the five branded sites a store item shows on - ticking Kid shows it on
  the Kid site's store, same mechanism the coach-profile brand fields
  already use, just read by the store instead.

- Item.custom_stock_qty (Int) - how many are currently in stock. Goes
  down as orders are fulfilled, editable directly by a Store Manager.

- Item.custom_unlimited_stock (Check) - for a digital download or a
  service that never "runs out" - when ticked, custom_stock_qty is
  ignored entirely and the item is always purchasable.

Safe to run more than once - create_custom_fields skips fields that
already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


ITEM_FIELDS = [
    {
        "fieldname": "custom_store_section",
        "fieldtype": "Section Break",
        "label": "Online Store",
        "insert_after": "custom_brand_school",
        "collapsible": 1,
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_store_enabled",
        "fieldtype": "Check",
        "label": "List in Online Store",
        "insert_after": "custom_store_section",
        "default": "0",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_unlimited_stock",
        "fieldtype": "Check",
        "label": "Always Available (unlimited stock)",
        "insert_after": "custom_store_enabled",
        "default": "0",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_stock_qty",
        "fieldtype": "Int",
        "label": "Stock Quantity",
        "insert_after": "custom_unlimited_stock",
        "default": "0",
        "depends_on": "eval:!doc.custom_unlimited_stock",
        "module": "Dashboard",
    },
]


def execute():
    create_custom_fields({"Item": ITEM_FIELDS}, ignore_validate=True)
    frappe.db.commit()
