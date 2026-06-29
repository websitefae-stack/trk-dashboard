"""
Background job handlers for calendar sync operations.
Each function is invoked via frappe.enqueue().
"""

import time

import frappe

from coach_calendar_sync.utils.google_calendar import (
    delete_event as _delete_google_event,
    push_event as _push_google_event,
)
from coach_calendar_sync.sync.logger import log_sync


def push_event(event_name: str):
    _run_with_logging(event_name, "Push", _do_push)


def cancel_event(event_name: str):
    _run_with_logging(event_name, "Cancel", _do_cancel)


def delete_event(event_name: str):
    _run_with_logging(event_name, "Delete", _do_delete)


# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────

def _do_push(event_doc):
    _push_google_event(event_doc)


def _do_cancel(event_doc):
    """Mark the Google event as cancelled (not deleted)."""
    from googleapiclient.discovery import build
    from coach_calendar_sync.utils.google_auth import get_credentials_for_person
    from coach_calendar_sync.utils.google_calendar import _get_person_info, _build_google_event

    doctype, name, calendar_id = _get_person_info(event_doc)
    if not doctype:
        return

    google_event_id = event_doc.get("custom_google_event_id")
    if not google_event_id:
        _push_google_event(event_doc)
        return

    creds = get_credentials_for_person(doctype, name)
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    body = _build_google_event(event_doc)
    body["status"] = "cancelled"
    service.events().update(
        calendarId=calendar_id,
        eventId=google_event_id,
        body=body,
        sendUpdates="none",
    ).execute()

    frappe.db.set_value(
        "Event", event_doc.name, "custom_sync_status", "Synced", update_modified=False
    )


def _do_delete(event_doc):
    _delete_google_event(event_doc)


def _run_with_logging(event_name: str, action: str, fn):
    start = time.monotonic()
    event_doc = frappe.get_doc("Event", event_name)
    coach = event_doc.custom_coach
    session_worker = event_doc.custom_session_worker

    try:
        fn(event_doc)
        duration = time.monotonic() - start
        log_sync(
            event=event_name,
            coach=coach,
            session_worker=session_worker,
            direction="Push",
            action=action,
            status="Success",
            google_event_id=frappe.db.get_value("Event", event_name, "custom_google_event_id"),
            duration=round(duration, 3),
        )
    except Exception as e:
        duration = time.monotonic() - start
        error = frappe.get_traceback()
        log_sync(
            event=event_name,
            coach=coach,
            session_worker=session_worker,
            direction="Push",
            action=action,
            status="Failed",
            error=str(e)[:500],
            duration=round(duration, 3),
        )
        frappe.log_error(error, f"Calendar Sync – {action} failed for {event_name}")
