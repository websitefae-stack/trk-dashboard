"""
Follow-up to v10 - pushes the latest Franchise Agreement text to the live
Practice Document again: Schedule 1's Transfer Fee line never actually
stated a figure (it ran straight into the general VAT note, as if that
note were describing the Transfer Fee itself) - Ashley confirmed the
figure is £1,500, now stated on its own line with the VAT note separated
out as the general Schedule-wide note it actually is.
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
