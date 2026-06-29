"""
API methods backing the Bulk Calendar Sync page.
"""

import frappe

from coach_calendar_sync.utils.google_calendar import push_event, delete_event
from coach_calendar_sync.sync.logger import log_sync


@frappe.whitelist()
def get_events(
    coach=None,
    session_worker=None,
    from_date=None,
    to_date=None,
    resync_existing=False,
    limit=500,
):
    """
    Return a list of Events matching the filters, ready for display
    in the Bulk Calendar Sync page.
    """
    frappe.only_for("System Manager")
    filters = {}
    if coach:
        filters["custom_coach"] = coach
    if session_worker:
        filters["custom_session_worker"] = session_worker
    if from_date:
        filters["starts_on"] = [">=", from_date]
    if to_date:
        filters["ends_on"] = ["<=", to_date]

    if not frappe.utils.cint(resync_existing):
        filters["custom_sync_status"] = ["!=", "Synced"]

    events = frappe.get_all(
        "Event",
        filters=filters,
        fields=[
            "name",
            "subject",
            "starts_on",
            "ends_on",
            "custom_coach",
            "custom_session_worker",
            "custom_sync_status",
            "custom_google_event_id",
        ],
        limit=int(limit),
        order_by="starts_on asc",
    )
    return events


@frappe.whitelist()
def sync_events(event_names: list, dry_run: bool = False):
    """
    Push a list of Event names to Google Calendar.
    If dry_run is True, return what would be synced without doing it.
    """
    frappe.only_for("System Manager")
    if isinstance(event_names, str):
        import json
        event_names = json.loads(event_names)

    results = {"success": [], "failed": [], "skipped": []}

    for event_name in event_names:
        doc = frappe.get_doc("Event", event_name)
        if not (doc.custom_coach or doc.custom_session_worker):
            results["skipped"].append({"name": event_name, "reason": "No coach or session worker"})
            continue

        if dry_run:
            results["success"].append({"name": event_name, "dry_run": True})
            continue

        try:
            push_event(doc)
            results["success"].append({"name": event_name})
        except Exception as e:
            results["failed"].append({"name": event_name, "error": str(e)})

    return results


@frappe.whitelist()
def delete_google_events(event_names: list, dry_run: bool = False):
    """Remove Google Calendar events for the given Frappe Event names."""
    frappe.only_for("System Manager")
    if isinstance(event_names, str):
        import json
        event_names = json.loads(event_names)

    results = {"success": [], "failed": [], "skipped": []}
    for event_name in event_names:
        doc = frappe.get_doc("Event", event_name)
        if not doc.custom_google_event_id:
            results["skipped"].append({"name": event_name, "reason": "No Google event ID"})
            continue
        if dry_run:
            results["success"].append({"name": event_name, "dry_run": True})
            continue
        try:
            delete_event(doc)
            results["success"].append({"name": event_name})
        except Exception as e:
            results["failed"].append({"name": event_name, "error": str(e)})

    return results


@frappe.whitelist()
def retry_failed():
    """Re-enqueue all failed events."""
    frappe.only_for("System Manager")
    failed = frappe.get_all(
        "Event", filters={"custom_sync_status": "Failed"}, pluck="name", limit=200
    )
    for name in failed:
        frappe.enqueue(
            "coach_calendar_sync.sync.worker.push_event",
            queue="short",
            timeout=120,
            event_name=name,
        )
    return len(failed)


@frappe.whitelist()
def get_dashboard_stats():
    """Return counts for the Calendar Sync Dashboard."""
    frappe.only_for("System Manager")

    connected_coaches = frappe.db.count("Coach", {"google_sync_enabled": 1, "connected": 1})
    connected_workers = frappe.db.count(
        "Session Worker", {"google_sync_enabled": 1, "connected": 1}
    )
    failed = frappe.db.count("Event", {"custom_sync_status": "Failed"})
    pending = frappe.db.count("Event", {"custom_sync_status": "Pending"})

    today_start = frappe.utils.get_datetime(frappe.utils.today())
    synced_today = frappe.db.count(
        "Calendar Sync Log",
        {"status": "Success", "creation": [">=", today_start]},
    )

    last_sync_row = frappe.db.get_value(
        "Calendar Sync Log",
        {"status": "Success"},
        "timestamp",
        order_by="timestamp desc",
    )

    return {
        "connected_coaches": connected_coaches,
        "connected_session_workers": connected_workers,
        "failed_syncs": failed,
        "pending_syncs": pending,
        "synced_today": synced_today,
        "last_sync": last_sync_row,
    }
