"""
Follow-up to v9 - pushes the latest Franchise Agreement text to the live
Practice Document again. Adds the substantive protections Ashley confirmed
from the same solicitor's review (safeguarding, liability, insurance, data
protection, mediation) plus the business decisions she made on the fee
holiday, Christmas break, franchisee termination right and multi-site
clients:

- Clause 2.4 (new) - multi-site clients (academy trusts etc) spanning more
  than one territory.
- Clause 2.1 amended and 4.3A (new) - the Marketing Fee is now actually
  required to be paid (it was defined and given a rate in Schedule 1 but
  no clause required payment of it) - a direct prerequisite for 4.12 below.
- Clause 4.11 replaced with a fixed Christmas Fee Holiday (16-31 December),
  and new clause 4.12 gives new franchisees their first three months,
  starting from when they actually begin operating.
- Clause 7.2 replaced (Enhanced DBS + Children's Barred List + ongoing
  reporting of investigations/allegations, not just convictions) and new
  clause 7.4 (ongoing safeguarding obligations) - the agreement previously
  had none beyond the initial DBS check.
- Clause 8.3.2 replaced - staff/subcontractors now need the same DBS
  clearance as the Franchisee herself before delivering Services.
- Clause 11.1 replaced - "all-risk" (property insurance) was the wrong
  product for a services business; now specifies public liability,
  professional indemnity, employers' liability and safeguarding cover.
- Clause 16.1.6 replaced - drops the outdated/potentially discriminatory
  Mental Health Act 1983 reference (genuine incapacity is already covered
  by clause 14.2) and fixes a missing "; or" that every sibling clause had.
- Clause 16.1.11 replaced - termination grounds now match the new 7.2/7.4
  safeguarding reporting obligations, not just a conviction.
- Clause 16.1.12.2 split into two distinct grounds for clarity - the
  7-day-remedy ground deliberately keeps its full original scope ("any
  breach of its obligations"), not narrowed to a single clause, per
  Ashley's explicit instruction not to narrow her own rights.
- New clause 16.3 - lets the Franchisor suspend a Franchisee mid-safeguarding
  investigation without having to terminate outright.
- New clause 16.4 - gives the Franchisee her own termination right, but
  only for the Franchisor's own uncured material breach of clauses 5/6.
- New clause 17.3.9 - social media/online accounts now transfer on exit,
  not just domains/website (clause 17.3.8 already covered those).
- Clause 17.4 replaced - drops the unenforceable "enter the Franchisee's
  premises without notice" right (many work from home) for a notify-third-
  parties approach instead.
- Clause 19A (new) - caps the Franchisor's own liability and excludes
  indirect losses, subject to what can never be excluded by law.
- Clause 17.1 (Survival) corrected - listed "clause 29" twice and omitted
  clause 19 entirely; now also includes the new 19A and matches which
  clauses should actually outlive termination.
- Clause 22 (Data Protection) rewritten for the current UK GDPR regime
  (the old text referenced the repealed 1998 Act's "seventh data
  protection principle") and adds a dedicated children's-data section,
  given this is a children's business. Clause 7.3.27.8's cross-reference
  updated to match.
- New clause 34.3 - mediation required before court proceedings (except
  urgent injunctive relief or IP/confidentiality protection).

Deliberately NOT included: the Transfer Fee figure (Ashley confirmed
Schedule 1 has never stated one and is leaving it as-is), and a few
smaller items flagged in the original review that weren't part of this
round (clause 18.1's "and"/grammar fixes, clause 32.1.1's outdated EU
regulation reference) - still outstanding if she wants them later.
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
