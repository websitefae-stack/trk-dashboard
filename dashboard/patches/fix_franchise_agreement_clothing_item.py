"""
Same clothing-range fix as fix_franchise_brochure_clothing_item.py, for
the Franchise Agreement Practice Document's Schedule 4 (Materials) -
"Soft shell jacket or Fleece or Body Warmer" -> "Hoodie or Sweatshirt".
Plain string replace on whatever's actually stored right now, so it
doesn't clobber the franchisor-signature/territory-map text already
pushed by update_franchise_agreement_practice_document_v3.
"""

import frappe

from dashboard.patches.add_franchise_agreement_practice_document import (
    FRANCHISE_AGREEMENT_TITLE,
    PRACTICE_DOCUMENT_DOCTYPE,
)

OLD_TEXT = "<li>Soft shell jacket or Fleece or Body Warmer</li>"
NEW_TEXT = "<li>Hoodie or Sweatshirt</li>"


def execute():
    name = frappe.db.get_value(PRACTICE_DOCUMENT_DOCTYPE, {"document_title": FRANCHISE_AGREEMENT_TITLE}, "name")
    if not name:
        return

    text = frappe.db.get_value(PRACTICE_DOCUMENT_DOCTYPE, name, "document_text") or ""
    if OLD_TEXT not in text:
        return

    frappe.db.set_value(PRACTICE_DOCUMENT_DOCTYPE, name, "document_text", text.replace(OLD_TEXT, NEW_TEXT))
    frappe.db.commit()
