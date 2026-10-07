"""
Adds the fields behind the "Franchise Agreement" e-signing flow - the
final Stage 1 contract, after Intent to Proceed and the Intake/DBS
form. Same shape as the franchisee NDA/Intent to Proceed flows
(add_franchise_lead_nda_fields.py / add_franchise_lead_intent_fields.py):
a public, token-linked page where the franchisee reads the agreement
and signs it by typing their name.

contract_commencement_date/territory_description/permitted_area are the
only commercial terms Ashley fills in the FIRST time she generates the
sign link for a lead (see leads.get_contract_sign_url) - per-deal,
decided by her, not something the franchisee ever types in. Fixed at
that point same as contract_agreement_date, so re-opening an
already-generated link always shows exactly what was originally sent.
contract_expiry_date is never typed in at all - it's computed as
exactly 3 years after contract_commencement_date (CONTRACT_TERM_YEARS
in leads.py), matching the Term defined in the agreement's own clause
1.1. Trade Name and the registered Trade Mark number aren't fields here
- they're fixed constants for this brand in the real agreement text
(see add_franchise_agreement_practice_document.py), not deal-specific.

contract_signed_snapshot is a frozen copy of the merged agreement text
at the moment of signing, not a live re-render - editing the master
template later never changes what someone already signed.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CLIENT_LEAD_FIELDS = [
    {
        "fieldname": "contract_token",
        "fieldtype": "Data",
        "label": "Franchise Agreement Sign Link Token",
        "read_only": 1,
        "unique": 1,
        "no_copy": 1,
        "insert_after": "stage1_final_invoice_date",
        "module": "Dashboard",
    },
    {
        "fieldname": "contract_agreement_date",
        "fieldtype": "Date",
        "label": "Franchise Agreement Date",
        "read_only": 1,
        "insert_after": "contract_token",
        "module": "Dashboard",
    },
    {
        "fieldname": "contract_commencement_date",
        "fieldtype": "Date",
        "label": "Commencement Date",
        "read_only": 1,
        "description": "Set by the franchisor when generating the sign link - fixed from then on for this lead.",
        "insert_after": "contract_agreement_date",
        "module": "Dashboard",
    },
    {
        "fieldname": "contract_expiry_date",
        "fieldtype": "Date",
        "label": "Expiry Date",
        "read_only": 1,
        "description": "Always exactly 3 years after the Commencement Date - computed, never typed in.",
        "insert_after": "contract_commencement_date",
        "module": "Dashboard",
    },
    {
        "fieldname": "contract_territory_description",
        "fieldtype": "Small Text",
        "label": "Territory",
        "read_only": 1,
        "insert_after": "contract_expiry_date",
        "module": "Dashboard",
    },
    {
        "fieldname": "contract_permitted_area",
        "fieldtype": "Data",
        "label": "Permitted Area",
        "read_only": 1,
        "insert_after": "contract_territory_description",
        "module": "Dashboard",
    },
    {
        "fieldname": "contract_sent_at",
        "fieldtype": "Datetime",
        "label": "Franchise Agreement Sent At",
        "read_only": 1,
        "insert_after": "contract_permitted_area",
        "module": "Dashboard",
    },
    {
        "fieldname": "contract_recipient_name",
        "fieldtype": "Data",
        "label": "Franchise Agreement Recipient Name",
        "read_only": 1,
        "insert_after": "contract_sent_at",
        "module": "Dashboard",
    },
    {
        "fieldname": "contract_recipient_address",
        "fieldtype": "Small Text",
        "label": "Franchise Agreement Recipient Address",
        "read_only": 1,
        "insert_after": "contract_recipient_name",
        "module": "Dashboard",
    },
    {
        "fieldname": "contract_signature_name",
        "fieldtype": "Data",
        "label": "Franchise Agreement Signature",
        "read_only": 1,
        "insert_after": "contract_recipient_address",
        "module": "Dashboard",
    },
    {
        "fieldname": "contract_signed_snapshot",
        "fieldtype": "Text Editor",
        "label": "Signed Franchise Agreement (Snapshot)",
        "read_only": 1,
        "description": "A frozen copy of the agreement text as it was at the moment of signing.",
        "insert_after": "contract_signature_name",
        "module": "Dashboard",
    },
    {
        "fieldname": "contract_signed_at",
        "fieldtype": "Datetime",
        "label": "Franchise Agreement Signed At",
        "read_only": 1,
        "insert_after": "contract_signed_snapshot",
        "module": "Dashboard",
    },
    {
        "fieldname": "contract_signer_ip",
        "fieldtype": "Data",
        "label": "Franchise Agreement Signer IP Address",
        "read_only": 1,
        "insert_after": "contract_signed_at",
        "module": "Dashboard",
    },
    {
        "fieldname": "contract_signer_user_agent",
        "fieldtype": "Small Text",
        "label": "Franchise Agreement Signer Browser/Device",
        "read_only": 1,
        "insert_after": "contract_signer_ip",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Client Lead"):
        return

    create_custom_fields({"Client Lead": CLIENT_LEAD_FIELDS}, ignore_validate=True)
    frappe.db.commit()
