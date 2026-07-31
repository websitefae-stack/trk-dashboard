"""
Adds the fields behind the franchisor's Item Access "Show on site" /
per-brand visibility feature:

- Item Default.custom_show_on_site (Check) - per coach/company, on top of
  the row's mere existence (which only ever governs invoice access - see
  invoices.get_link_options("Item")). A coach's public profile pages only
  ever show a service they've been explicitly ticked "Show on site" for,
  never just because they have access to sell it.

- Item.custom_brand_hub / _kid / _teen / _people / _school (Check) - which
  of resilient_domains' five branded coach-profile sites (trh/trk/trt/trp/
  trs) this item/service is even relevant to at all, independent of which
  coach's showing it (e.g. CPD Training might only ever be a School/Hub
  service, never Kid/Teen/People).

Both are independent of each other - a coach only sees a service on their
own public profile once ALL of: they have access (Item Default row
exists), that row's custom_show_on_site is ticked, AND the item's own
brand flag for that particular site is ticked too.

Safe to run more than once - create_custom_fields skips fields that
already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


ITEM_DEFAULT_FIELDS = [
    {
        "fieldname": "custom_show_on_site",
        "fieldtype": "Check",
        "label": "Show on Site",
        "insert_after": "default_price_list",
        "default": "0",
        "module": "Dashboard",
    },
]

ITEM_FIELDS = [
    {
        "fieldname": "custom_brand_section",
        "fieldtype": "Section Break",
        "label": "Public Website Brands",
        "insert_after": "description",
        "collapsible": 1,
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_brand_hub",
        "fieldtype": "Check",
        "label": "The Resilient Hub",
        "insert_after": "custom_brand_section",
        "default": "0",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_brand_kid",
        "fieldtype": "Check",
        "label": "The Resilient Kid",
        "insert_after": "custom_brand_hub",
        "default": "0",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_brand_teen",
        "fieldtype": "Check",
        "label": "The Resilient Teen",
        "insert_after": "custom_brand_kid",
        "default": "0",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_brand_people",
        "fieldtype": "Check",
        "label": "The Resilient People",
        "insert_after": "custom_brand_teen",
        "default": "0",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_brand_school",
        "fieldtype": "Check",
        "label": "The Resilient School",
        "insert_after": "custom_brand_people",
        "default": "0",
        "module": "Dashboard",
    },
]


def execute():
    create_custom_fields({"Item Default": ITEM_DEFAULT_FIELDS}, ignore_validate=True)
    create_custom_fields({"Item": ITEM_FIELDS}, ignore_validate=True)
    frappe.db.commit()
