"""
Follow-up to v3 - pushes the latest Franchise Agreement text to the live
Practice Document again, per a real franchisee's queries on the signed
agreement:

1. Clause 1.1's Term definition said three (3) years, but clause 3.2's
   renewal right was for a further five (5) years - inconsistent about
   how long the INITIAL term actually runs. Changed to five (5) years
   throughout: the Term definition, clause 13.2 (a buyer's replacement
   franchise term on a sale of the business), and Schedule 1's Expiry
   Date note. CONTRACT_TERM_YEARS (leads.py/recruitment_leads.py, which
   computes expiry_date = commencement_date + CONTRACT_TERM_YEARS rather
   than asking Ashley to type it in) is changed to 5 alongside this, so
   the computed Expiry Date actually matches what the text now says.

2. Clause 4.8 didn't say whether the Initial Fee/Management Fee/
   Marketing Fee in Schedule 1 are VAT-exclusive on top of being quoted
   net - added that the Franchisor isn't currently VAT registered, and
   what happens (VAT added from that date, on written notice) if that
   changes. Also fixed "Al fees" -> "All fees". Schedule 1 gets a short
   pointer to the same clause.

3. Clause 7.3.27.12 required a dedicated business land line - asked
   whether a mobile number counts. Now reads "a dedicated business
   landline or dedicated business mobile number".

Only ever applies to a lead's Franchise Agreement signed AFTER this
patch runs - an already-signed agreement's contract_signed_snapshot is
a frozen copy taken at sign time and is correctly left untouched here.
The wording changes here reach any already-generated-but-not-yet-signed
sign link the next time it's loaded (get_contract_preview always
renders live from this text), but NOT its already-computed
contract_expiry_date - that's only ever recalculated when the
franchisor generates a link for the first time or explicitly clicks
"Update Terms" (update_contract_terms), so an in-flight link still
shows the old three-years-out date until one of those runs again.
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
