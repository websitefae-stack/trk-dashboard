"""
Adds a "Territory Postcode Areas" field to Coach, where office records the
postcode areas/districts (e.g. "N1, N2, NW3") a coach is assigned to cover
- used by the franchisor Client Locations map to draw each coach's
territory and flag clients who fall outside their own coach's area, or
inside another coach's.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

COACH_FIELDS = [
    {
        "fieldname": "territory_postcodes",
        "fieldtype": "Small Text",
        "label": "Territory Postcode Areas",
        "description": (
            "Comma-separated postcode areas/districts this coach covers, e.g. \"N1, N2, NW3\" - "
            "not full postcodes, just the area/district prefix."
        ),
        "insert_after": "linked_client",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Coach"):
        return

    create_custom_fields({"Coach": COACH_FIELDS}, ignore_validate=True)
    frappe.db.commit()
