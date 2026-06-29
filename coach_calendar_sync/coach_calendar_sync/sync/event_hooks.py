"""
Frappe doc_events hooks for the Event DocType.
These run synchronously on save/cancel/delete, but immediately hand off
to background jobs so the UI is never blocked.
"""

import frappe


def _enqueue(method: str, event_name: str):
    frappe.enqueue(
        f"coach_calendar_sync.sync.worker.{method}",
        queue="short",
        timeout=120,
        event_name=event_name,
        now=frappe.flags.in_test,
    )


def after_insert(doc, method=None):
    if not _is_syncable(doc):
        return
    frappe.db.set_value("Event", doc.name, "custom_sync_status", "Pending", update_modified=False)
    _enqueue("push_event", doc.name)


def on_update(doc, method=None):
    if not _is_syncable(doc):
        return
    frappe.db.set_value("Event", doc.name, "custom_sync_status", "Pending", update_modified=False)
    _enqueue("push_event", doc.name)


def on_cancel(doc, method=None):
    if not _is_syncable(doc):
        return
    _enqueue("cancel_event", doc.name)


def on_trash(doc, method=None):
    if not _is_syncable(doc):
        return
    _enqueue("delete_event", doc.name)


def _is_syncable(doc) -> bool:
    if getattr(doc.flags, "ignore_calendar_sync", False):
        return False
    return bool(doc.custom_coach or doc.custom_session_worker)
