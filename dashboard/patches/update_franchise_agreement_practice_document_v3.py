"""
Follow-up to v2 - pushes the latest Franchise Agreement text to the live
Practice Document again: the TRK logo at the top and in Schedule 3 (the
Trade Mark itself), a real per-deal Territory map image (via the new
contract_territory_map Attach Image field), and Ashley's own typed
signature ({{ franchisor_signature }}) in place of the hardcoded "AJC"
that was effectively pre-signing the agreement on her behalf with no
real sign action or audit trail. See
add_franchise_agreement_signing_and_uploads.py and
add_franchise_agreement_practice_document.py's own docstring for the
full reasoning.
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
