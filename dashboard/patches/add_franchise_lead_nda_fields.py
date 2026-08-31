"""
Adds the fields behind the franchisee NDA e-signing flow directly onto
Client Lead - a public, token-linked page (no login) where a franchisee
reads the NDA (pulled live from its Practice Document template, see
add_franchisee_nda_practice_document.py) and signs it by typing their
name. One signature per lead, so plain fields rather than a child table.

nda_token is the unbindable secret in the link sent to them - anyone
who knows it can view/sign, so it's a long random hash, generated once,
never guessable from the lead's own name (see leads.get_nda_sign_url).

nda_signed_snapshot is deliberately a frozen copy of the merged
agreement text at the moment they signed, not a live re-render of the
template - if Ashley edits the master text next year, everyone who
already signed keeps exactly what they actually agreed to.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CLIENT_LEAD_FIELDS = [
    {
        "fieldname": "nda_token",
        "fieldtype": "Data",
        "label": "NDA Sign Link Token",
        "read_only": 1,
        "unique": 1,
        "no_copy": 1,
        "insert_after": "stage1_agreement_invoice_date",
        "module": "Dashboard",
    },
    {
        "fieldname": "nda_agreement_date",
        "fieldtype": "Date",
        "label": "NDA Agreement Date",
        "read_only": 1,
        "description": (
            "Set once, the first time a sign link is generated for this lead - the \"made and entered "
            "into on\" date shown in the agreement (and the Franchisor's own signing date), which stays "
            "fixed even if the franchisee doesn't actually sign until later."
        ),
        "insert_after": "nda_token",
        "module": "Dashboard",
    },
    {
        "fieldname": "nda_recipient_name",
        "fieldtype": "Data",
        "label": "NDA Recipient Name",
        "read_only": 1,
        "insert_after": "nda_agreement_date",
        "module": "Dashboard",
    },
    {
        "fieldname": "nda_recipient_address",
        "fieldtype": "Small Text",
        "label": "NDA Recipient Address",
        "read_only": 1,
        "insert_after": "nda_recipient_name",
        "module": "Dashboard",
    },
    {
        "fieldname": "nda_signature_name",
        "fieldtype": "Data",
        "label": "NDA Signature",
        "read_only": 1,
        "insert_after": "nda_recipient_address",
        "module": "Dashboard",
    },
    {
        "fieldname": "nda_term_expiry",
        "fieldtype": "Date",
        "label": "NDA Term Expiry",
        "read_only": 1,
        "description": "3 years from the date signed.",
        "insert_after": "nda_signature_name",
        "module": "Dashboard",
    },
    {
        "fieldname": "nda_signed_snapshot",
        "fieldtype": "Text Editor",
        "label": "Signed NDA (Snapshot)",
        "read_only": 1,
        "description": "A frozen copy of the agreement text as it was at the moment of signing.",
        "insert_after": "nda_term_expiry",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Client Lead"):
        return

    create_custom_fields({"Client Lead": CLIENT_LEAD_FIELDS}, ignore_validate=True)
    frappe.db.commit()
