"""
Adds a "pack sent" tickbox to Client, right after Address - reads as "The
Resilient Kid Pack sent" or "The Resilient Teen Pack sent" depending on
the client's own client_type (see build_field()'s special-case for this
fieldname in client_details.py), since a client is always one or the
other, never both.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CLIENT_FIELDS = [
    {
        "fieldname": "custom_resilient_pack_sent",
        "fieldtype": "Check",
        "label": "Resilient Pack Sent",
        "default": "0",
        "insert_after": "address",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Client"):
        return

    create_custom_fields({"Client": CLIENT_FIELDS}, ignore_validate=True)
    frappe.db.commit()
