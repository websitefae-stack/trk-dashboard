"""
Follow-up to v7 - pushes the latest Franchise Agreement text to the live
Practice Document again. Fixes applied in this round (from Ashley's own
review of a solicitor's amendment schedule):

- Clause 4.7's bank sort code and account number were transposed (a sort
  code is 6 digits/XX-XX-XX, an account number is 8 digits) - swapped
  back to the correct values.
- Schedule 1's Management Fee table had £1,500 in both the 10% and 8%
  bands - the first band now stops at £1,499.
- "the Brand" was used in clauses 2.3 and 8.2 but never defined - now
  defined in clause 1.1 as the collective group of trading names, and
  clause 2.3's stray "under the Name" (not itself a defined term)
  corrected to "under the Trade Name".
- Clause 8.6 contradicted clause 4.1/5.1.5 (Initial Fee covers clause 5,
  which includes initial training) by saying all training is charged
  separately - now says initial training is included in the Initial Fee,
  with only further/refresher/staff training charged.
- "customer(s)" replaced with "client(s)" throughout, case-preserving -
  the business refers to the people it serves as clients, not customers.
- Two missing spaces after a colon in running prose (Schedule 1's
  Management Fee and Marketing Fee lines) corrected.
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
