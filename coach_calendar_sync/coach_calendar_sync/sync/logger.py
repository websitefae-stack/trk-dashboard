"""
Helpers for writing Calendar Sync Log entries.
"""

import frappe


def log_sync(
    event: str = None,
    coach: str = None,
    session_worker: str = None,
    direction: str = "Push",
    action: str = "Sync",
    status: str = "Success",
    google_event_id: str = None,
    error: str = None,
    duration: float = None,
):
    try:
        doc = frappe.new_doc("Calendar Sync Log")
        doc.event = event
        doc.coach = coach
        doc.session_worker = session_worker
        doc.direction = direction
        doc.action = action
        doc.status = status
        doc.google_event_id = google_event_id
        doc.error = error
        doc.duration = duration
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Calendar Sync Log – write failed")
