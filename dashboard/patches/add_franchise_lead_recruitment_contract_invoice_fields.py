"""
Adds 3 more Stage 1 - Decide & Commit milestones to Client Lead, after
the existing 5 from add_franchise_lead_stage1_fields.py: Ashley's own
recruitment review (the References form + her own assessment), sending
the full franchise contract, and raising the final invoice - these
currently happen, but only informally/outside the system, after the
intake step and before HQ starts onboarding (creating the coach's
email, "Your Logins" hub, ordering clothing, etc). Plain Check + Date
pairs, same as every other Stage 1 milestone - no automation behind
them (Ashley does the contract/invoice manually, same as she already
does for the deposit invoice), this is tracking only.

Franchisee-only (same depends_on as the existing Stage 1 fields) - a
Session Worker lead's own (shorter) onboarding checklist in leads.py's
SESSION_WORKER_STAGE_MILESTONES deliberately doesn't gain these.

Confirmed with Ashley these aren't meant to block "Convert to Client" -
some leads reach this point after already being converted (the deposit
invoice already raised separately), so this just tracks on the lead
rather than gating anything.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

FRANCHISEE_DEPENDS_ON = "eval:doc.appointment_type && doc.appointment_type.toLowerCase().indexOf('franchisee call') !== -1"

CLIENT_LEAD_FIELDS = [
    {
        "fieldname": "stage1_recruitment_questions_done",
        "fieldtype": "Check",
        "label": "Recruitment Questions Reviewed",
        "description": "References received and Ashley's own assessment complete - happy to proceed.",
        "insert_after": "stage1_agreement_invoice_date",
        "depends_on": FRANCHISEE_DEPENDS_ON,
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_recruitment_questions_date",
        "fieldtype": "Date",
        "label": "Date",
        "insert_after": "stage1_recruitment_questions_done",
        "depends_on": FRANCHISEE_DEPENDS_ON,
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_col_5",
        "fieldtype": "Column Break",
        "insert_after": "stage1_recruitment_questions_date",
        "depends_on": FRANCHISEE_DEPENDS_ON,
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_contract_sent_done",
        "fieldtype": "Check",
        "label": "Full Contract Signed",
        "description": "Auto-ticked once the franchisee signs the Franchise Agreement (see leads.sign_contract) - same as Sign NDA/Intent to Proceed above.",
        "insert_after": "stage1_col_5",
        "depends_on": FRANCHISEE_DEPENDS_ON,
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_contract_sent_date",
        "fieldtype": "Date",
        "label": "Date",
        "insert_after": "stage1_contract_sent_done",
        "depends_on": FRANCHISEE_DEPENDS_ON,
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_col_6",
        "fieldtype": "Column Break",
        "insert_after": "stage1_contract_sent_date",
        "depends_on": FRANCHISEE_DEPENDS_ON,
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_final_invoice_done",
        "fieldtype": "Check",
        "label": "Final Invoice Raised",
        "insert_after": "stage1_col_6",
        "depends_on": FRANCHISEE_DEPENDS_ON,
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_final_invoice_date",
        "fieldtype": "Date",
        "label": "Date",
        "insert_after": "stage1_final_invoice_done",
        "depends_on": FRANCHISEE_DEPENDS_ON,
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Client Lead"):
        return

    create_custom_fields({"Client Lead": CLIENT_LEAD_FIELDS}, ignore_validate=True)
    frappe.db.commit()
