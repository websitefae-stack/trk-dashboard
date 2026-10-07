"""
Follow-up to add_franchise_agreement_practice_document.py - that patch
only ever creates the "Franchise Agreement" Practice Document and
early-returns once it already exists, so it never picked up Ashley's
detailed corrections against her real .docx (2026-10): date/franchisee
name added to the cover and execution pages, franchisee name+address on
the Parties clause, a new "fees may increase" note in Schedule 1,
Schedule 1's duplicate/broken "Permitted Name" lines consolidated into
one ("The Resilient Kid ({{ permitted_area }})"), Schedule 2 showing the
Commencement/Expiry Date alongside the Territory, and a real Materials
list in Schedule 4. Directly overwrites the live document_text with the
same content the source patch now creates fresh installs with, so the
two can't drift apart.
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
