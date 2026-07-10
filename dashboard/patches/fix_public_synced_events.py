"""
One-time cleanup: coach_calendar_sync's Google Calendar import
(_upsert_pulled_event in puller.py) created Events without setting
event_type, so they defaulted to "Public" - making every synced appointment
visible/reminder-eligible to every coach via Frappe's native daily events
reminder, not just the coach it belongs to. The sync code now sets
event_type = "Private" going forward; this patch flips any Events that were
already created Public before that fix, and shares each one with the
dashboard admin accounts so they keep full visibility in the raw Frappe
backend without needing Public.

Runs automatically on the next `bench migrate` (part of a normal deploy) -
no manual step needed.
"""

import frappe

from dashboard.api.shared.calendar import DASHBOARD_ADMIN_USERS


def execute():
    event_names = frappe.get_all("Event", filters={"event_type": "Public"}, pluck="name")

    for name in event_names:
        try:
            frappe.db.set_value("Event", name, "event_type", "Private", update_modified=False)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Fix Public Synced Events - set Private - {name}")
            continue

        _share_with_admins(name)

    frappe.db.commit()


def _share_with_admins(event_name):
    for user in DASHBOARD_ADMIN_USERS:
        try:
            if not frappe.db.exists("User", user):
                continue
            frappe.share.add_docshare(
                "Event",
                event_name,
                user,
                read=1,
                write=1,
                notify=0,
                flags={"ignore_share_permission": True},
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Fix Public Synced Events - share - {event_name}")
