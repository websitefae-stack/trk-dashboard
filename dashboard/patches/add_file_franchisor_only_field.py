"""
Adds "Franchisor Only" onto Frappe's core File doctype - lets a file
uploaded to a Client's Files tab (e.g. a franchisee's contract on their
own linked_client record) be tagged so only the franchisor dashboard
shows it, not the coach dashboard. See client_details.get_client_files
(reads it) and upload_client_file (sets it).
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

FILE_FIELDS = [
    {
        "fieldname": "custom_franchisor_only",
        "fieldtype": "Check",
        "label": "Franchisor Only",
        "description": "Only show this file on the franchisor dashboard, not to coaches.",
        "insert_after": "is_private",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "File"):
        return

    create_custom_fields({"File": FILE_FIELDS}, ignore_validate=True)
    frappe.db.commit()
