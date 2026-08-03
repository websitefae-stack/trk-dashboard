"""
One-time catch-up for any Practice Document that already has Linked
Items set (via the Frappe Desk, before item_access.py's on_update hook
existed to keep this in sync automatically) - forces Resource
Availability to "Selected Coaches" and reconciles the coach list against
current Item Access, exactly what saving the document again would now
do on its own. Without this, a document linked to an item before this
patch landed would stay wide open to every coach until someone happened
to resave it.

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
            frappe.log_error(frappe.get_traceback(), f"Resync Practice Document Resource Access - {name}")

    frappe.db.commit()
