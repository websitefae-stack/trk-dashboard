"""
Adds the fields behind the franchisee's own Intake + DBS/Insurance form -
Stage 1's 4th milestone (see add_franchise_lead_stage1_fields.py),
alongside the Deposit and Intent to Proceed sign flow. A public,
token-linked page (no login) where the franchisee gives her personal
details and uploads her DBS certificate (required) and, optionally,
another supporting document (e.g. proof of insurance).

Deliberately prefixed franchisee_intake_ rather than intake_ - "intake"
on Client Lead already means something else entirely (the general
client-enquiry "Intake Doctype" Web Form, see leads.py's own INTAKE_*
constants) and this must never collide with or be confused for that.

franchisee_intake_dbs_certificate/franchisee_intake_additional_document
are private Attach fields - only ever reachable by someone who already
has permission to open this Client Lead (see leads.upload_franchisee_
intake_file), never public files.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CLIENT_LEAD_FIELDS = [
    {
        "fieldname": "franchisee_intake_token",
        "fieldtype": "Data",
        "label": "Franchisee Intake Form Token",
        "read_only": 1,
        "unique": 1,
        "no_copy": 1,
        "insert_after": "intent_signer_user_agent",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_submitted",
        "fieldtype": "Check",
        "label": "Franchisee Intake Form Submitted",
        "read_only": 1,
        "insert_after": "franchisee_intake_token",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_submitted_at",
        "fieldtype": "Datetime",
        "label": "Franchisee Intake Form Submitted At",
        "read_only": 1,
        "insert_after": "franchisee_intake_submitted",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_first_name",
        "fieldtype": "Data",
        "label": "First Name",
        "read_only": 1,
        "insert_after": "franchisee_intake_submitted_at",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_last_name",
        "fieldtype": "Data",
        "label": "Last Name",
        "read_only": 1,
        "insert_after": "franchisee_intake_first_name",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_phone",
        "fieldtype": "Data",
        "label": "Phone",
        "read_only": 1,
        "insert_after": "franchisee_intake_last_name",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_gender",
        "fieldtype": "Select",
        "label": "Gender",
        "options": "\nFemale\nMale\nNon-binary\nPrefer not to say\nOther",
        "read_only": 1,
        "insert_after": "franchisee_intake_phone",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_dob",
        "fieldtype": "Date",
        "label": "Date of Birth",
        "read_only": 1,
        "insert_after": "franchisee_intake_gender",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_dbs_number",
        "fieldtype": "Data",
        "label": "DBS Certificate Number",
        "read_only": 1,
        "insert_after": "franchisee_intake_dob",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_dbs_date_received",
        "fieldtype": "Date",
        "label": "DBS Date Received",
        "read_only": 1,
        "insert_after": "franchisee_intake_dbs_number",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_dbs_expiry_date",
        "fieldtype": "Date",
        "label": "DBS Expiry Date",
        "read_only": 1,
        "insert_after": "franchisee_intake_dbs_date_received",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_dbs_certificate",
        "fieldtype": "Attach",
        "label": "DBS Certificate",
        "read_only": 1,
        "insert_after": "franchisee_intake_dbs_expiry_date",
        "module": "Dashboard",
    },
    {
        "fieldname": "franchisee_intake_additional_document",
        "fieldtype": "Attach",
        "label": "Additional Document (e.g. Proof of Insurance)",
        "read_only": 1,
        "insert_after": "franchisee_intake_dbs_certificate",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Client Lead"):
        return

    create_custom_fields({"Client Lead": CLIENT_LEAD_FIELDS}, ignore_validate=True)
    frappe.db.commit()
