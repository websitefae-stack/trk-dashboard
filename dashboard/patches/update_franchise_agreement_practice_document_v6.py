"""
Follow-up to v5 - pushes the latest Franchise Agreement text to the live
Practice Document again, per Ashley's own urgent flag: the agreement
had a "Resilient Teen" Addendum baked straight into the end of the main
Kid agreement (right after clause 34, before Schedule 1) - every Kid
franchisee signing the main agreement was also implicitly being shown
Teen addendum text (an extra £4000 initial fee, "Business" redefined
to include The Resilient Teen, its own franchisor/franchisee signature
lines), regardless of whether they had anything to do with Teen at all.

Confirmed with Ashley: Kid is the one real agreement; Teen is a
separate, optional additional franchise a Kid coach can choose to take
on later, paid for and agreed to separately - it was never meant to be
part of the Kid agreement at all, let alone unconditionally. Removed
the whole Addendum section. A real, standalone Teen agreement (its own
document, own price field) is a separate, later piece of work, not
this patch.
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
