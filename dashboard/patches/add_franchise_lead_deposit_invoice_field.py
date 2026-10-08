"""
Adds a "Deposit Invoice Done" Stage 1 milestone (Check + Date) to Client
Lead, right after Intent to Proceed - Ashley's own existing
stage1_intent_deposit_dbs_done field bundles "Intent to Proceed" with
the deposit invoice and DBS into one tick, but its label only ever shows
"Intent to Proceed", with no separate way to track the deposit invoice
itself. This is a distinct, plain Check + Date pair, same as every other
Stage 1 milestone - no automation behind it (Ashley raises this invoice
manually), tracking only.

Franchisee-only (same depends_on as the existing Stage 1 fields) - a
Session Worker lead's own (shorter) onboarding checklist in leads.py's
SESSION_WORKER_STAGE_MILESTONES doesn't gain this.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

FRANCHISEE_DEPENDS_ON = "eval:doc.appointment_type && doc.appointment_type.toLowerCase().indexOf('franchisee call') !== -1"

CLIENT_LEAD_FIELDS = [
    {
        "fieldname": "stage1_deposit_invoice_done",
        "fieldtype": "Check",
        "label": "Deposit Invoice Done",
        "insert_after": "stage1_intent_deposit_dbs_date",
        "depends_on": FRANCHISEE_DEPENDS_ON,
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_deposit_invoice_date",
        "fieldtype": "Date",
        "label": "Date",
        "insert_after": "stage1_deposit_invoice_done",
        "depends_on": FRANCHISEE_DEPENDS_ON,
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Client Lead"):
        return

    create_custom_fields({"Client Lead": CLIENT_LEAD_FIELDS}, ignore_validate=True)
    frappe.db.commit()
