"""
Adds a "Date of Birth" field directly onto Coach, so a coach with no
linked_client (or whose linked_client has no date_of_birth set - see
dashboard.py's _get_coach_birthday_rows) has somewhere to record their
own birthday at all. _get_coach_birthday_rows already prefers this
field over the linked_client fallback whenever it's present and set -
no other code change needed for it to start showing up on the
Upcoming Birthdays widget once filled in.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

COACH_FIELDS = [
    {
        "fieldname": "date_of_birth",
        "fieldtype": "Date",
        "label": "Date of Birth",
        "insert_after": "coach_name",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Coach"):
        return

    create_custom_fields({"Coach": COACH_FIELDS}, ignore_validate=True)
    frappe.db.commit()
