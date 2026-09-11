"""
Creates "Franchise Brochure" as a single (one record, no list) custom
DocType with a rich-text Content field - Ashley edits the franchise
brochure here in Desk any time content changes, instead of re-exporting
and re-uploading a PDF. Rendered at resilient_domains'
/franchise-brochure page (noindex, not in any sitemap - reachable only
via direct link), which also offers a print/"Download PDF" button.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe

DOCTYPE_NAME = "Franchise Brochure"


def execute():
    if frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": DOCTYPE_NAME,
        "module": "Dashboard",
        "custom": 1,
        "issingle": 1,
        "fields": [
            {
                "fieldname": "content",
                "fieldtype": "Text Editor",
                "label": "Brochure Content",
                "description": "Edit this any time - the live brochure page always shows whatever is saved here.",
            },
        ],
        "permissions": [
            {
                "role": "System Manager",
                "read": 1, "write": 1, "print": 1, "email": 1, "share": 1,
            },
        ],
    })
    doc.insert(ignore_permissions=True)
