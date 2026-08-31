"""
Adds an audit trail to the franchisee NDA e-signing flow (see
add_franchise_lead_nda_fields.py) - IP address, browser/device (User
Agent), and a precise signed timestamp, captured automatically at the
moment someone actually submits the sign form. The same kind of evidence
a real e-signature service (DocuSign etc.) records alongside a typed
signature, for if the agreement is ever disputed.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CLIENT_LEAD_FIELDS = [
    {
        "fieldname": "nda_signed_at",
        "fieldtype": "Datetime",
        "label": "NDA Signed At",
        "read_only": 1,
        "insert_after": "nda_signed_snapshot",
        "module": "Dashboard",
    },
    {
        "fieldname": "nda_signer_ip",
        "fieldtype": "Data",
        "label": "NDA Signer IP Address",
        "read_only": 1,
        "insert_after": "nda_signed_at",
        "module": "Dashboard",
    },
    {
        "fieldname": "nda_signer_user_agent",
        "fieldtype": "Small Text",
        "label": "NDA Signer Browser/Device",
        "read_only": 1,
        "insert_after": "nda_signer_ip",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Client Lead"):
        return

    create_custom_fields({"Client Lead": CLIENT_LEAD_FIELDS}, ignore_validate=True)
    frappe.db.commit()
