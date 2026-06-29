"""
Scheduled task that runs every 5 minutes.
"""

import frappe

from coach_calendar_sync.sync.puller import pull_for_all


def run_sync_cycle():
    """Push pending events, pull from Google, retry failures."""
    _push_pending()
    _retry_failed()
    pull_for_all()


def _push_pending():
    pending = frappe.get_all(
        "Event",
        filters={"custom_sync_status": "Pending"},
        fields=["name"],
    )
    for row in pending:
        frappe.enqueue(
            "coach_calendar_sync.sync.worker.push_event",
            queue="short",
            timeout=120,
            event_name=row["name"],
        )


def _retry_failed():
    settings = frappe.get_single("Calendar Sync Settings")
    retry_count = int(settings.retry_count or 3)

    failed = frappe.get_all(
        "Event",
        filters={"custom_sync_status": "Failed"},
        fields=["name"],
        limit=50,
    )
    # Simple strategy: enqueue each one; the worker will update status
    for row in failed[:retry_count * 10]:
        frappe.enqueue(
            "coach_calendar_sync.sync.worker.push_event",
            queue="short",
            timeout=120,
            event_name=row["name"],
        )
