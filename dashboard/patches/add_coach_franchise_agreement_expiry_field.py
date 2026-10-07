"""
Adds custom_franchise_agreement_expiry_date to Coach - a simple, plainly
visible note on the franchisor's Coach Details page of when this
coach's Franchise Agreement term ends (always 3 years from its
Commencement Date - see leads.get_contract_sign_url's CONTRACT_TERM_
YEARS). Ashley fills this in by hand once she creates the real Coach
record (Stage 2), since that's a manual step with no link back to the
originating Client Lead's own contract_expiry_date.

Deliberately just a visible note, not a reminder/renewal workflow -
there's no "what happens as this date approaches" process built yet;
Ashley asked for the visibility first, flagging the follow-up workflow
as a known, separate, not-yet-built next step.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

COACH_FIELDS = [
    {
        "fieldname": "custom_franchise_agreement_expiry_date",
        "fieldtype": "Date",
        "label": "Franchise Agreement Expiry Date",
        "description": "From the signed Franchise Agreement (Commencement Date + 3 years) - set by hand, no automatic reminder yet.",
        "insert_after": "pricelist",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Coach"):
        return

    create_custom_fields({"Coach": COACH_FIELDS}, ignore_validate=True)
    frappe.db.commit()
