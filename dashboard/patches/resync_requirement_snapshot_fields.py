"""
One-time catch-up for sync_requirement_snapshot_fields (see hooks.py's
Practice Document on_update doc_events, and its own docstring) - a
Practice Document edited before that hook existed could have left some
of its still-open Coach Document Requirement rows showing a stale
required_action/mandatory/declaration text snapshot from whenever they
were first assigned, which is exactly why some policies were showing a
signature block and others weren't for what should be the same
current setting. Re-runs the same resync for every existing Practice
Document so already-created requirements catch up too, not just future
edits.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Practice Document") or not frappe.db.exists("DocType", "Coach Document Requirement"):
        return

    from dashboard.api.shared.practice_documents import sync_requirement_snapshot_fields

    practice_document_names = frappe.get_all("Practice Document", pluck="name")

    for name in practice_document_names:
        try:
            doc = frappe.get_doc("Practice Document", name)
            sync_requirement_snapshot_fields(doc)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Resync Requirement Snapshot Fields - {name}")

    frappe.db.commit()
