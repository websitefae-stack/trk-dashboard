"""
Follow-up to v8 - pushes the latest Franchise Agreement text to the live
Practice Document again: the Website definition's url was misspelt and
pointed at the wrong domain ("theresilientacadamy.co.uk") - corrected to
theresilientkid.co.uk, confirmed by Ashley.
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
