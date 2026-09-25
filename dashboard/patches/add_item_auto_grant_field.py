"""
See item_access.py's "AUTO-GRANTING A NEW SERVICE TO EVERY COACH"
section - custom_auto_granted_coach_access marks that a service Item's
one-off auto-grant (Access + Show on Site, every coach) has already run,
so the Item.on_update hook never re-runs it and silently undoes a
coach's access being deliberately revoked by hand later.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ITEM_FIELDS = [
    {
        "fieldname": "custom_auto_granted_coach_access",
        "fieldtype": "Check",
        "label": "Auto-Granted Coach Access",
        "description": "Set automatically the first time this service was given to every coach - never shown/edited by hand.",
        "insert_after": "custom_coach_price",
        "hidden": 1,
        "module": "Dashboard",
    },
]


def execute():
    if frappe.db.exists("DocType", "Item"):
        create_custom_fields({"Item": ITEM_FIELDS}, ignore_validate=True)

    frappe.db.commit()
