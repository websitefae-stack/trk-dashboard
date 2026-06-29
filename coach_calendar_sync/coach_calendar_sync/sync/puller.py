"""
Pull events from Google Calendar into Frappe Events.
Avoids duplicates using the custom_google_event_id field.
"""

import frappe

from coach_calendar_sync.utils.google_calendar import pull_events_for_person
from coach_calendar_sync.sync.logger import log_sync


def pull_for_all():
    """Pull from all enabled coaches and session workers."""
    for doctype in ("Coach", "Session Worker"):
        for name in frappe.get_all(
            doctype,
            filters={"google_sync_enabled": 1, "connected": 1},
            pluck="name",
        ):
            try:
                pull_for_person(doctype, name)
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Calendar Pull – {doctype} {name}")


def pull_for_person(doctype: str, name: str, time_min=None, time_max=None):
    google_events = pull_events_for_person(doctype, name, time_min=time_min, time_max=time_max)
    imported = 0
    updated = 0

    for g_event in google_events:
        g_id = g_event.get("id")
        private_props = (g_event.get("extendedProperties") or {}).get("private") or {}

        # Skip events that Frappe created (we already have them)
        if private_props.get("frappe_event_id"):
            continue

        existing = frappe.db.get_value(
            "Event", {"custom_google_event_id": g_id}, "name"
        )

        start = g_event.get("start", {})
        end = g_event.get("end", {})
        starts_on = start.get("dateTime") or start.get("date")
        ends_on = end.get("dateTime") or end.get("date")

        if existing:
            doc = frappe.get_doc("Event", existing)
            doc.subject = g_event.get("summary", doc.subject)
            doc.description = g_event.get("description", doc.description)
            doc.location = g_event.get("location", doc.location)
            doc.starts_on = starts_on
            doc.ends_on = ends_on
            doc.flags.ignore_calendar_sync = True
            doc.save(ignore_permissions=True)
            updated += 1
        else:
            doc = frappe.new_doc("Event")
            doc.subject = g_event.get("summary") or "(No title)"
            doc.description = g_event.get("description", "")
            doc.location = g_event.get("location", "")
            doc.starts_on = starts_on
            doc.ends_on = ends_on
            doc.custom_google_event_id = g_id
            doc.custom_sync_status = "Synced"

            if doctype == "Coach":
                doc.custom_coach = name
            else:
                doc.custom_session_worker = name

            doc.flags.ignore_calendar_sync = True
            doc.insert(ignore_permissions=True)
            imported += 1

    frappe.db.commit()
    log_sync(
        coach=name if doctype == "Coach" else None,
        session_worker=name if doctype == "Session Worker" else None,
        direction="Pull",
        action="Pull",
        status="Success",
    )
    return {"imported": imported, "updated": updated}
