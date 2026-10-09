"""
Follow-up to v4 - pushes the latest Franchise Agreement text to the live
Practice Document again, per Ashley's own readability feedback on v4's
changes: every clause number ran straight into the clause text with no
separating punctuation ("7.3.27.2supply the Franchisor..."), making the
whole document hard to scan. Every numbered <p> and <h4> throughout the
template now has ". " (or, for an <h4> whose number already had a dot
but no space, just the missing space) inserted between the number and
the text that follows - e.g. "7.3.27.2. supply the Franchisor...",
"1. INTERPRETATION".

Also splits two places where two separate sub-clauses had been run
together inside a single <p> with no paragraph break at all (13.5.3/
13.6, and 16.1.2/16.1.3) - same readability issue, just a paragraph
break rather than a missing space.

Purely a formatting pass - no wording, figures or legal terms changed
beyond what v4 already changed.
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
