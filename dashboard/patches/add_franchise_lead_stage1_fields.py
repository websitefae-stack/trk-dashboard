"""
Adds the Stage 1 - Decide & Commit pipeline fields to Client Lead - the
5 pre-hire milestones between someone booking a Franchisee Call and HQ
creating their real Coach record (Stage 2 onward, already built - see
onboarding.py). Plain Check + Date pairs directly on the lead rather than
a master-step/instance system like Coach Onboarding Step: that
architecture exists because HQ's coach onboarding list is long and
changes over time, where this is a short, fixed, well-known 5-item list
that doesn't need per-item Desk editing.

Shown only on a Franchisee Call lead (see lead_details.js) - a normal
client enquiry never has a use for these.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CLIENT_LEAD_FIELDS = [
    {
        "fieldname": "stage1_section",
        "fieldtype": "Section Break",
        "label": "Stage 1 - Decide & Commit",
        "insert_after": "converted_contact",
        "depends_on": "eval:doc.appointment_type && doc.appointment_type.toLowerCase().indexOf('franchisee call') !== -1",
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_call_done",
        "fieldtype": "Check",
        "label": "Call With Ashley (Founder) / Franchise Call",
        "insert_after": "stage1_section",
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_call_date",
        "fieldtype": "Date",
        "label": "Call Date",
        "insert_after": "stage1_call_done",
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_col_1",
        "fieldtype": "Column Break",
        "insert_after": "stage1_call_date",
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_nda_done",
        "fieldtype": "Check",
        "label": "Sign NDA",
        "insert_after": "stage1_col_1",
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_nda_date",
        "fieldtype": "Date",
        "label": "NDA Signed Date",
        "insert_after": "stage1_nda_done",
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_col_2",
        "fieldtype": "Column Break",
        "insert_after": "stage1_nda_date",
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_discovery_day_done",
        "fieldtype": "Check",
        "label": "Discovery Day",
        "insert_after": "stage1_col_2",
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_discovery_day_date",
        "fieldtype": "Date",
        "label": "Discovery Day Date",
        "insert_after": "stage1_discovery_day_done",
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_col_3",
        "fieldtype": "Column Break",
        "insert_after": "stage1_discovery_day_date",
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_intent_deposit_dbs_done",
        "fieldtype": "Check",
        "label": "Intent to Proceed + Deposit + DBS/Insurance Submitted",
        "description": "This is the point a real Client record (type Franchise) gets created for billing.",
        "insert_after": "stage1_col_3",
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_intent_deposit_dbs_date",
        "fieldtype": "Date",
        "label": "Date",
        "insert_after": "stage1_intent_deposit_dbs_done",
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_col_4",
        "fieldtype": "Column Break",
        "insert_after": "stage1_intent_deposit_dbs_date",
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_agreement_invoice_done",
        "fieldtype": "Check",
        "label": "Franchisee Agreement Signed + Final Invoice Paid",
        "description": "Once ticked, Stage 1 is complete - go create the real Coach record to begin Stage 2.",
        "insert_after": "stage1_col_4",
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_agreement_invoice_date",
        "fieldtype": "Date",
        "label": "Date",
        "insert_after": "stage1_agreement_invoice_done",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Client Lead"):
        return

    create_custom_fields({"Client Lead": CLIENT_LEAD_FIELDS}, ignore_validate=True)
    frappe.db.commit()
