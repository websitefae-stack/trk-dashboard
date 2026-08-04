"""
Undoes fix_workshop_resource_document_purpose.py - that patch (and the
resync logic it called) pushed every Workshop Resource document's
Document Purpose to "Client Resource" so it would appear on a coach's
Documents page, but Workshop Resources are meant to stay Internal
Compliance and internal-only, gated purely by Item Access - not
shareable with clients the way a real Client Resource document is.
_get_visible_resource_documents() (practice_documents.py) now surfaces
Workshop Resource documents regardless of Document Purpose, so this is
no longer needed to make them visible - only to undo the wrong value
this app previously wrote.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Practice Document"):
        return

    if not frappe.get_meta("Practice Document").has_field("document_purpose"):
        return

    document_names = frappe.get_all(
        "Practice Document",
        filters={
            "document_type": "Workshop Resource",
            "document_purpose": "Client Resource",
        },
        pluck="name",
    )

    for name in document_names:
        frappe.db.set_value(
            "Practice Document", name, "document_purpose", "Internal Compliance",
            update_modified=False,
        )

    frappe.db.commit()
