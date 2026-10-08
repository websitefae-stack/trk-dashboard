"""
Follow-up to create_recruitment_lead_doctype.py - that patch only ever
creates the "Recruitment Lead" doctype and early-returns once it already
exists (frappe.db.exists("DocType", DOCTYPE_NAME): return), so several
fields added by LATER edits to its own field list (deposit invoice
milestone, franchisor e-sign fields, territory map upload) never
actually reached the live site once the doctype had already been
created by an earlier deploy - confirmed live: uploading a Territory
Map Image failed outright (frappe.db.set_value against a column that
didn't exist), and the franchisor's own typed/auto-captured signature
was silently never being saved (doc.attr = value; doc.save() no-ops for
an unknown field rather than erroring, unlike a direct db.set_value).

Uses the same safe, idempotent create_custom_fields() approach as every
other "add a field that might already be live" patch in this app -
never touches a field that's already there, regardless of whether this
is a fresh install or a site that already has some (but not all) of
these.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

DOCTYPE_NAME = "Recruitment Lead"

RECRUITMENT_LEAD_FIELDS = [
    {
        "fieldname": "stage1_deposit_invoice_done",
        "fieldtype": "Check",
        "label": "Deposit Invoice Done",
        "insert_after": "stage1_intent_deposit_dbs_date",
        "depends_on": "eval:doc.lead_type=='Franchisee'",
        "module": "Dashboard",
    },
    {
        "fieldname": "stage1_deposit_invoice_date",
        "fieldtype": "Date",
        "label": "Date",
        "insert_after": "stage1_deposit_invoice_done",
        "depends_on": "eval:doc.lead_type=='Franchisee'",
        "module": "Dashboard",
    },
    {
        "fieldname": "contract_franchisor_signature_name",
        "fieldtype": "Small Text",
        "label": "Franchisor Signature",
        "read_only": 1,
        "insert_after": "contract_signer_user_agent",
        "module": "Dashboard",
    },
    {
        "fieldname": "contract_franchisor_signed_at",
        "fieldtype": "Datetime",
        "label": "Franchisor Signed At",
        "read_only": 1,
        "insert_after": "contract_franchisor_signature_name",
        "module": "Dashboard",
    },
    {
        "fieldname": "contract_franchisor_signer_ip",
        "fieldtype": "Small Text",
        "label": "Franchisor Signer IP",
        "read_only": 1,
        "insert_after": "contract_franchisor_signed_at",
        "module": "Dashboard",
    },
    {
        "fieldname": "contract_franchisor_signer_user_agent",
        "fieldtype": "Small Text",
        "label": "Franchisor Signer Browser/Device",
        "read_only": 1,
        "insert_after": "contract_franchisor_signer_ip",
        "module": "Dashboard",
    },
    {
        "fieldname": "contract_territory_map",
        "fieldtype": "Attach Image",
        "label": "Territory Map Image",
        "description": "Shown in Schedule 2 - upload the area map for this franchisee's postcode territory before generating the sign link.",
        "insert_after": "contract_franchisor_signer_user_agent",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    create_custom_fields({DOCTYPE_NAME: RECRUITMENT_LEAD_FIELDS}, ignore_validate=True)
    frappe.db.commit()
