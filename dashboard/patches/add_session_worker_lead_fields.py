"""
Fields behind the Session Worker onboarding pipeline (see leads.py's
is_session_worker_lead/SESSION_WORKER_STAGE_MILESTONES) - a lead who signs
the NDA and fills in the same Franchisee Intake + DBS form as a
franchisee (a few extra self-report fields below, shown only on that
form for a Session Worker lead), then signs a Fees and Expectations
Guide with their sponsoring Coach (the lead's own `coach` field), then
is finally set up as a real Session Worker record by hand in Desk (see
get_session_worker_setup_url/set_session_worker_link - Session Worker
is a doctype this app doesn't own, so this app never auto-inserts one).

franchisee_intake_qualifications/work_locations/public_liability_insurer/
indemnity_insurer/insurance_renewal_date are the self-report data points
pulled from the Safer Recruitment Checklist - deliberately only the
worker-supplied ones (DBS/insurance/qualifications/work area). The
checklist's verification/sign-off columns (identity checked, references
followed up, induction completed, etc.) are a separate internal
franchisor/coach compliance record, not something a worker self-reports,
so they're out of scope here.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CLIENT_LEAD_FIELDS = [
    # Session-worker-only self-report additions to the shared Franchisee
    # Intake + DBS/Insurance form.
    {
        "fieldname": "franchisee_intake_qualifications",
        "fieldtype": "Small Text",
        "label": "Relevant Qualifications / Training",
        "read_only": 1,
        "insert_after": "franchisee_intake_sent_at",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_work_locations",
        "fieldtype": "Data",
        "label": "Main Work Locations / Areas",
        "read_only": 1,
        "insert_after": "franchisee_intake_qualifications",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_public_liability_insurer",
        "fieldtype": "Data",
        "label": "Public Liability Insurer & Policy Number",
        "read_only": 1,
        "insert_after": "franchisee_intake_work_locations",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_indemnity_insurer",
        "fieldtype": "Data",
        "label": "Professional Indemnity Insurer & Policy Number",
        "read_only": 1,
        "insert_after": "franchisee_intake_public_liability_insurer",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_insurance_renewal_date",
        "fieldtype": "Date",
        "label": "Insurance Policy Renewal Date",
        "read_only": 1,
        "insert_after": "franchisee_intake_indemnity_insurer",
        "module": "Dashboard",
    },
    # Fees and Expectations Guide e-signing - worker + sponsoring coach.
    {
        "fieldname": "fees_guide_token",
        "fieldtype": "Data",
        "label": "Fees and Expectations Guide Token",
        "read_only": 1,
        "unique": 1,
        "no_copy": 1,
        "insert_after": "franchisee_intake_insurance_renewal_date",
        "module": "Dashboard",
    },
    {
        "fieldname": "fees_guide_sent_at",
        "fieldtype": "Datetime",
        "label": "Fees and Expectations Guide Sent At",
        "read_only": 1,
        "no_copy": 1,
        "insert_after": "fees_guide_token",
        "module": "Dashboard",
    },
    {
        "fieldname": "fees_guide_agreement_date",
        "fieldtype": "Date",
        "label": "Fees and Expectations Guide Effective From",
        "read_only": 1,
        "insert_after": "fees_guide_sent_at",
        "module": "Dashboard",
    },
    {
        "fieldname": "fees_guide_rate_1to1",
        "fieldtype": "Currency",
        "label": "Session Rate - 1:1 Individual",
        "read_only": 1,
        "insert_after": "fees_guide_agreement_date",
        "module": "Dashboard",
    },
    {
        "fieldname": "fees_guide_rate_group",
        "fieldtype": "Currency",
        "label": "Session Rate - Small Group",
        "read_only": 1,
        "insert_after": "fees_guide_rate_1to1",
        "module": "Dashboard",
    },
    {
        "fieldname": "fees_guide_rate_workshop",
        "fieldtype": "Currency",
        "label": "Session Rate - School / Workshop",
        "read_only": 1,
        "insert_after": "fees_guide_rate_group",
        "module": "Dashboard",
    },
    {
        "fieldname": "fees_guide_invoicing_frequency",
        "fieldtype": "Select",
        "label": "Invoicing Frequency",
        "options": "\nWeekly\nFortnightly\nMonthly",
        "read_only": 1,
        "insert_after": "fees_guide_rate_workshop",
        "module": "Dashboard",
    },
    {
        "fieldname": "fees_guide_recipient_name",
        "fieldtype": "Data",
        "label": "Fees and Expectations Guide Recipient Name",
        "read_only": 1,
        "insert_after": "fees_guide_invoicing_frequency",
        "module": "Dashboard",
    },
    {
        "fieldname": "fees_guide_signature_name",
        "fieldtype": "Data",
        "label": "Fees and Expectations Guide Signature",
        "read_only": 1,
        "insert_after": "fees_guide_recipient_name",
        "module": "Dashboard",
    },
    {
        "fieldname": "fees_guide_signed_snapshot",
        "fieldtype": "Text Editor",
        "label": "Fees and Expectations Guide Signed Snapshot",
        "read_only": 1,
        "no_copy": 1,
        "insert_after": "fees_guide_signature_name",
        "module": "Dashboard",
    },
    {
        "fieldname": "fees_guide_signed_at",
        "fieldtype": "Datetime",
        "label": "Fees and Expectations Guide Signed At",
        "read_only": 1,
        "no_copy": 1,
        "insert_after": "fees_guide_signed_snapshot",
        "module": "Dashboard",
    },
    {
        "fieldname": "fees_guide_signer_ip",
        "fieldtype": "Data",
        "label": "Fees and Expectations Guide Signer IP",
        "read_only": 1,
        "no_copy": 1,
        "insert_after": "fees_guide_signed_at",
        "module": "Dashboard",
    },
    {
        "fieldname": "fees_guide_signer_user_agent",
        "fieldtype": "Data",
        "label": "Fees and Expectations Guide Signer Browser/Device",
        "read_only": 1,
        "no_copy": 1,
        "insert_after": "fees_guide_signer_ip",
        "module": "Dashboard",
    },
    {
        "fieldname": "fees_guide_done",
        "fieldtype": "Check",
        "label": "Fees and Expectations Guide Signed",
        "read_only": 1,
        "insert_after": "fees_guide_signer_user_agent",
        "module": "Dashboard",
    },
    {
        "fieldname": "fees_guide_date",
        "fieldtype": "Date",
        "label": "Fees and Expectations Guide Signed Date",
        "read_only": 1,
        "insert_after": "fees_guide_done",
        "module": "Dashboard",
    },
    # Final "Set Up As Session Worker" milestone - manual, since Session
    # Worker is created by hand in Desk (see get_session_worker_setup_url).
    {
        "fieldname": "sw_setup_done",
        "fieldtype": "Check",
        "label": "Set Up As Session Worker",
        "insert_after": "fees_guide_date",
        "module": "Dashboard",
    },
    {
        "fieldname": "sw_setup_date",
        "fieldtype": "Date",
        "label": "Set Up As Session Worker Date",
        "insert_after": "sw_setup_done",
        "module": "Dashboard",
    },
    {
        "fieldname": "converted_session_worker",
        "fieldtype": "Link",
        "options": "Session Worker",
        "label": "Session Worker Record",
        "read_only": 1,
        "no_copy": 1,
        "insert_after": "sw_setup_date",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Client Lead"):
        return

    create_custom_fields({"Client Lead": CLIENT_LEAD_FIELDS}, ignore_validate=True)
    frappe.db.commit()
