"""
Adds "sent at" tracking for the three Stage 1 compose-before-send email
flows (NDA, Intent to Proceed, Franchisee Intake + DBS form) - separate
from each flow's own *_signed_at / *_submitted_at fields, which only get
set once the franchisee actually acts on the link. These are set purely
by Ashley clicking Send (or Resend) in the compose modal - see leads.py's
send_nda_link/send_intent_link/send_franchisee_intake_form.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CLIENT_LEAD_FIELDS = [
    {
        "fieldname": "nda_sent_at",
        "fieldtype": "Datetime",
        "label": "NDA Sent At",
        "read_only": 1,
        "no_copy": 1,
        "insert_after": "nda_token",
        "module": "Dashboard",
    },
    {
        "fieldname": "intent_sent_at",
        "fieldtype": "Datetime",
        "label": "Intent to Proceed Sent At",
        "read_only": 1,
        "no_copy": 1,
        "insert_after": "intent_token",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_sent_at",
        "fieldtype": "Datetime",
        "label": "Franchisee Intake Form Sent At",
        "read_only": 1,
        "no_copy": 1,
        "insert_after": "franchisee_intake_token",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Client Lead"):
        return

    create_custom_fields({"Client Lead": CLIENT_LEAD_FIELDS}, ignore_validate=True)
    frappe.db.commit()
