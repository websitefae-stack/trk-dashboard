"""
Follow-up to v11 - pushes the latest Franchise Agreement text to the live
Practice Document again. The two remaining items from the solicitor's
review:

- Clause 18.1's opening words were missing "and", leaving it ambiguous
  whether the restriction applies during the Agreement too or only after
  termination - fixed, and also fixes clause 18.1.1's "any of the or
  other franchisees" grammar error.
- Clause 32.1.1 cited Commission Regulation No. 330/2010, which expired
  31 May 2022 - replaced with its actual UK successor, the Competition
  Act 1998 (Vertical Agreements Block Exemption) Order 2022.
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
