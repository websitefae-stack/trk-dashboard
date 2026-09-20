"""
Adds the fields behind the "Deposit and Intent to Proceed Agreement"
e-signing flow - the Stage 1 step between Discovery Day and the
Intake/DBS form (see add_franchise_lead_stage1_fields.py's milestone 4).
Same shape as the franchisee NDA flow (add_franchise_lead_nda_fields.py):
a public, token-linked page where the franchisee reads the agreement and
signs it by typing their name.

intent_territory/intent_deposit_amount/intent_end_date are the business
terms Ashley fills in the FIRST time she generates the sign link for a
lead (see leads.get_intent_sign_url) - they're per-deal, decided by her,
not something the franchisee ever types in. Fixed at that point same as
intent_agreement_date, so re-opening an already-generated link always
shows exactly what was originally sent, even if these values change on
other leads afterwards.

intent_signed_snapshot is a frozen copy of the merged agreement text at
the moment of signing, not a live re-render - editing the master
template later never changes what someone already signed.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CLIENT_LEAD_FIELDS = [
    {
        "fieldname": "intent_token",
        "fieldtype": "Data",
        "label": "Intent to Proceed Sign Link Token",
        "read_only": 1,
        "unique": 1,
        "no_copy": 1,
        "insert_after": "nda_signer_user_agent",
        "module": "Dashboard",
    },
    {
        "fieldname": "intent_agreement_date",
        "fieldtype": "Date",
        "label": "Intent to Proceed Agreement Date",
        "read_only": 1,
        "insert_after": "intent_token",
        "module": "Dashboard",
    },
    {
        "fieldname": "intent_territory",
        "fieldtype": "Data",
        "label": "Territory",
        "read_only": 1,
        "description": "Set by the franchisor when generating the sign link - fixed from then on for this lead.",
        "insert_after": "intent_agreement_date",
        "module": "Dashboard",
    },
    {
        "fieldname": "intent_deposit_amount",
        "fieldtype": "Currency",
        "label": "Deposit Amount",
        "read_only": 1,
        "insert_after": "intent_territory",
        "module": "Dashboard",
    },
    {
        "fieldname": "intent_end_date",
        "fieldtype": "Date",
        "label": "Agreement End Date (if no Franchise Agreement by then)",
        "read_only": 1,
        "insert_after": "intent_deposit_amount",
        "module": "Dashboard",
    },
    {
        "fieldname": "intent_recipient_name",
        "fieldtype": "Data",
        "label": "Intent to Proceed Recipient Name",
        "read_only": 1,
        "insert_after": "intent_end_date",
        "module": "Dashboard",
    },
    {
        "fieldname": "intent_recipient_address",
        "fieldtype": "Small Text",
        "label": "Intent to Proceed Recipient Address",
        "read_only": 1,
        "insert_after": "intent_recipient_name",
        "module": "Dashboard",
    },
    {
        "fieldname": "intent_signature_name",
        "fieldtype": "Data",
        "label": "Intent to Proceed Signature",
        "read_only": 1,
        "insert_after": "intent_recipient_address",
        "module": "Dashboard",
    },
    {
        "fieldname": "intent_signed_snapshot",
        "fieldtype": "Text Editor",
        "label": "Signed Intent to Proceed (Snapshot)",
        "read_only": 1,
        "description": "A frozen copy of the agreement text as it was at the moment of signing.",
        "insert_after": "intent_signature_name",
        "module": "Dashboard",
    },
    {
        "fieldname": "intent_signed_at",
        "fieldtype": "Datetime",
        "label": "Intent to Proceed Signed At",
        "read_only": 1,
        "insert_after": "intent_signed_snapshot",
        "module": "Dashboard",
    },
    {
        "fieldname": "intent_signer_ip",
        "fieldtype": "Data",
        "label": "Intent to Proceed Signer IP Address",
        "read_only": 1,
        "insert_after": "intent_signed_at",
        "module": "Dashboard",
    },
    {
        "fieldname": "intent_signer_user_agent",
        "fieldtype": "Small Text",
        "label": "Intent to Proceed Signer Browser/Device",
        "read_only": 1,
        "insert_after": "intent_signer_ip",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Client Lead"):
        return

    create_custom_fields({"Client Lead": CLIENT_LEAD_FIELDS}, ignore_validate=True)
    frappe.db.commit()
