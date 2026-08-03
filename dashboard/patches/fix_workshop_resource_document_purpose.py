"""
Follow-up to resync_practice_document_resource_access.py - that patch
reconciled Resource Availability/coach lists for documents that already
had Linked Items set, but at the time _resync_practice_document_coaches()
didn't yet also push Document Purpose to "Client Resource". A document
left on the default "Internal Compliance" purpose never appears on a
coach's own Documents page no matter how correctly its Resource
Availability/coach list is set, since _get_visible_resource_documents()
only ever looks at Client Resource/Both documents in the first place.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Practice Document") or not frappe.db.exists("DocType", "Practice Document Item"):
        return

    if not frappe.get_meta("Practice Document").has_field("linked_items"):
        return

    from dashboard.api.shared.item_access import _resync_practice_document_coaches

    practice_document_names = frappe.get_all(
        "Practice Document Item",
        filters={"parenttype": "Practice Document"},
        pluck="parent",
        distinct=True,
    )

    for name in practice_document_names:
        try:
            _resync_practice_document_coaches(name)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Fix Workshop Resource Document Purpose - {name}")

    frappe.db.commit()
