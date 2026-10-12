"""
Follow-up to v6 - pushes the latest Franchise Agreement text to the live
Practice Document again: Schedule 1's Initial Fee line was a hardcoded
"£5,999 (less any deposit paid)" for every franchisee regardless of
their actual deal - now {{ initial_fee_details }}, a real per-lead
field (see add_contract_initial_fee_details_field.py) so a specific
discount or part-paid deposit (e.g. Sam's) can actually be reflected on
her own contract, defaulting to that same standard wording when left
blank.
"""

import frappe

from dashboard.patches.add_franchise_agreement_practice_document import (
    PRACTICE_DOCUMENT_DOCTYPE,
    FRANCHISE_AGREEMENT_TITLE,
    FRANCHISE_AGREEMENT_TEMPLATE_TEXT,
)


def execute():
    name = frappe.db.get_value(PRACTICE_DOCUMENT_DOCTYPE, {"document_title": FRANCHISE_AGREEMENT_TITLE}, "name")
    if not name:
        return

    frappe.db.set_value(PRACTICE_DOCUMENT_DOCTYPE, name, "document_text", FRANCHISE_AGREEMENT_TEMPLATE_TEXT)
    frappe.db.commit()
