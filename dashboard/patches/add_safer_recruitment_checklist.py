"""
Digitises the "Session Worker Onboarding & Safer Recruitment Checklist"
document in full, for BOTH lead kinds that go through the shared
Franchisee Intake + DBS/Insurance form (a Franchisee Call and a Session
Worker - see leads.is_onboarding_pipeline_lead), not just session
workers - a potential franchisee delivering sessions needs the same
safeguarding checks.

Two halves, matching how the checklist's rows naturally split:

1. Self-report additions to the shared intake form (franchisee_intake_*
   below) - what the worker/franchisee can state about themselves
   (ID document held, right to work status, address history, overseas
   checks if any, work history, and two references' contact details).
   The qualifications/insurance fields from add_session_worker_lead_
   fields.py already covered the rest of the self-reportable ground and
   are no longer session-worker-only (see leads.py's submit_franchisee_
   intake) - shown on the form for both lead kinds now.

2. safer_recruitment_checklist - a Table field (Safer Recruitment
   Checklist Item child doctype) the FRANCHISOR fills in after intake is
   submitted: one row per verification item from the document (Identity
   verified, DBS application submitted, references obtained, training
   completed, etc.), each with a Status (Pending/Complete/N/A) + Date +
   Checked By + Notes - exactly the document's own Status/Date/Checked
   by/Notes columns. Rows are seeded on first read (see leads.get_safer_
   recruitment_checklist) rather than by this patch, since seeding here
   would need to touch every existing lead row-by-row for no benefit.
   safer_recruitment_outstanding_actions is a free-text catch-all for the
   document's final "Outstanding actions and conditions" table, which has
   no fixed rows of its own.

A Table field itself adds no column to Client Lead's row (child table
rows live in their own table) - see the add_session_worker_lead_fields.py
patch's note on why every other new field here is Small Text/short
Data rather than a bare 140-byte Data column: Client Lead is right at
MariaDB's row-size ceiling and there's no headroom to spend carelessly.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CLIENT_LEAD_FIELDS = [
    {
        "fieldname": "franchisee_intake_id_document_type",
        "fieldtype": "Small Text",
        "label": "ID Document Provided (e.g. Passport, Driving Licence)",
        "read_only": 1,
        "insert_after": "franchisee_intake_insurance_renewal_date",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_right_to_work_status",
        "fieldtype": "Select",
        "length": 30,
        "label": "Right to Work Status",
        "options": "\nBritish/Irish Citizen\nSettled/Pre-Settled Status\nVisa - Right to Work\nTo Be Confirmed",
        "read_only": 1,
        "insert_after": "franchisee_intake_id_document_type",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_right_to_work_expiry",
        "fieldtype": "Date",
        "label": "Right to Work / Visa Expiry (if applicable)",
        "read_only": 1,
        "insert_after": "franchisee_intake_right_to_work_status",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_address_history",
        "fieldtype": "Small Text",
        "label": "Address History (Last 5 Years)",
        "read_only": 1,
        "insert_after": "franchisee_intake_right_to_work_expiry",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_overseas_checks",
        "fieldtype": "Small Text",
        "label": "Overseas Police Clearance / Working With Children Check (if applicable)",
        "read_only": 1,
        "insert_after": "franchisee_intake_address_history",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_work_history",
        "fieldtype": "Small Text",
        "label": "Relevant Work History / Experience",
        "read_only": 1,
        "insert_after": "franchisee_intake_overseas_checks",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_reference1_details",
        "fieldtype": "Small Text",
        "label": "Reference 1 - Name, Relationship & Contact Details",
        "read_only": 1,
        "insert_after": "franchisee_intake_work_history",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_reference2_details",
        "fieldtype": "Small Text",
        "label": "Reference 2 - Name, Relationship & Contact Details",
        "read_only": 1,
        "insert_after": "franchisee_intake_reference1_details",
        "module": "Dashboard",
    },
    {
        "fieldname": "safer_recruitment_checklist",
        "fieldtype": "Table",
        "options": "Safer Recruitment Checklist Item",
        "label": "Safer Recruitment Checklist",
        "insert_after": "franchisee_intake_reference2_details",
        "module": "Dashboard",
    },
    {
        "fieldname": "safer_recruitment_outstanding_actions",
        "fieldtype": "Small Text",
        "label": "Outstanding Actions & Conditions",
        "insert_after": "safer_recruitment_checklist",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Client Lead"):
        return

    # Not gated on "Safer Recruitment Checklist Item" already existing -
    # create_custom_fields() only records a Custom Field row pointing at
    # that doctype by name, it doesn't need the doctype's own table to
    # exist yet. That table is created by the ordinary app-doctype JSON
    # sync (dashboard/dashboard/doctype/safer_recruitment_checklist_item/)
    # that every `bench migrate` already does regardless of this patches
    # list, whichever order the two happen to run in.
    create_custom_fields({"Client Lead": CLIENT_LEAD_FIELDS}, ignore_validate=True)
    frappe.db.commit()
