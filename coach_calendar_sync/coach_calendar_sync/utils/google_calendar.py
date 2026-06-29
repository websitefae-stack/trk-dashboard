"""
Thin wrapper around the Google Calendar API v3.
"""

import frappe
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from coach_calendar_sync.utils.google_auth import get_credentials_for_person

MEET_SESSION_TYPES = {"Therapy Session", "Parent Check-In", "Initial Consultation"}
MEET_LOCATION_KEYWORDS = {"google meet", "online", "virtual"}


def _build_service(doctype: str, name: str):
    creds = get_credentials_for_person(doctype, name)
    if not creds:
        frappe.throw(f"No valid Google credentials for {doctype} {name}")
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _wants_meet(event_doc) -> bool:
    session_type = getattr(event_doc, "custom_session_type", None) or ""
    location = (event_doc.location or "").lower()
    return (
        session_type in MEET_SESSION_TYPES
        or any(kw in location for kw in MEET_LOCATION_KEYWORDS)
    )


def _build_google_event(event_doc) -> dict:
    """Convert a Frappe Event doc to a Google Calendar event body."""
    location = (
        event_doc.custom_therapy_location_address
        or event_doc.location
        or ""
    )

    body = {
        "summary": event_doc.subject,
        "description": event_doc.description or "",
        "location": location,
        "start": {
            "dateTime": frappe.utils.get_datetime(event_doc.starts_on).isoformat(),
            "timeZone": frappe.utils.get_system_timezone(),
        },
        "end": {
            "dateTime": frappe.utils.get_datetime(event_doc.ends_on).isoformat(),
            "timeZone": frappe.utils.get_system_timezone(),
        },
        "status": "confirmed" if event_doc.status != "Cancelled" else "cancelled",
        "extendedProperties": {
            "private": {
                "frappe_event_id": event_doc.name,
                "frappe_site": frappe.local.site,
            }
        },
    }

    if _wants_meet(event_doc):
        body["conferenceData"] = {
            "createRequest": {
                "requestId": f"frappe-{event_doc.name}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }

    return body


def _get_person_info(event_doc):
    """Return (doctype, name, calendar_id) for the event's owner."""
    if event_doc.custom_coach:
        doc = frappe.get_doc("Coach", event_doc.custom_coach)
        return "Coach", event_doc.custom_coach, doc.google_calendar_id
    elif event_doc.custom_session_worker:
        doc = frappe.get_doc("Session Worker", event_doc.custom_session_worker)
        return "Session Worker", event_doc.custom_session_worker, doc.google_calendar_id
    return None, None, None


def push_event(event_doc) -> str | None:
    """
    Create or update the Google Calendar event for the given Frappe Event.
    Returns the Google Event ID.
    """
    doctype, name, calendar_id = _get_person_info(event_doc)
    if not doctype:
        return None

    service = _build_service(doctype, name)
    body = _build_google_event(event_doc)
    google_event_id = event_doc.get("custom_google_event_id")

    want_meet = _wants_meet(event_doc)
    conference_version = 1 if want_meet else 0

    try:
        if google_event_id:
            result = service.events().update(
                calendarId=calendar_id,
                eventId=google_event_id,
                body=body,
                conferenceDataVersion=conference_version,
                sendUpdates="none",
            ).execute()
        else:
            result = service.events().insert(
                calendarId=calendar_id,
                body=body,
                conferenceDataVersion=conference_version,
                sendUpdates="none",
            ).execute()

        google_event_id = result.get("id")

        # Capture Meet URL if present
        meet_url = None
        conf = result.get("conferenceData", {})
        for ep in conf.get("entryPoints", []):
            if ep.get("entryPointType") == "video":
                meet_url = ep.get("uri")
                break

        updates = {
            "custom_google_event_id": google_event_id,
            "custom_sync_status": "Synced",
            "custom_last_sync_error": None,
        }
        if meet_url:
            updates["custom_google_meet_url"] = meet_url

        frappe.db.set_value("Event", event_doc.name, updates, update_modified=False)
        return google_event_id

    except HttpError as e:
        error_msg = str(e)
        frappe.db.set_value(
            "Event",
            event_doc.name,
            {"custom_sync_status": "Failed", "custom_last_sync_error": error_msg[:500]},
            update_modified=False,
        )
        raise


def delete_event(event_doc):
    """Cancel/delete the Google Calendar event."""
    doctype, name, calendar_id = _get_person_info(event_doc)
    if not doctype:
        return

    google_event_id = event_doc.get("custom_google_event_id")
    if not google_event_id:
        return

    service = _build_service(doctype, name)
    try:
        service.events().delete(
            calendarId=calendar_id,
            eventId=google_event_id,
            sendUpdates="none",
        ).execute()
        frappe.db.set_value(
            "Event",
            event_doc.name,
            {"custom_google_event_id": None, "custom_sync_status": "Synced"},
            update_modified=False,
        )
    except HttpError as e:
        if e.resp.status == 410:
            # Already deleted on Google's side — that's fine
            frappe.db.set_value(
                "Event", event_doc.name, "custom_google_event_id", None, update_modified=False
            )
        else:
            raise


def pull_events_for_person(doctype: str, name: str, time_min=None, time_max=None) -> list[dict]:
    """Fetch events from Google Calendar for one person."""
    doc = frappe.get_doc(doctype, name)
    if not doc.google_sync_enabled or not doc.google_calendar_id:
        return []

    service = _build_service(doctype, name)
    calendar_id = doc.google_calendar_id

    params = {
        "calendarId": calendar_id,
        "singleEvents": True,
        "orderBy": "startTime",
        "privateExtendedProperty": f"frappe_site={frappe.local.site}",
    }
    if time_min:
        params["timeMin"] = time_min
    if time_max:
        params["timeMax"] = time_max

    events = []
    page_token = None
    while True:
        if page_token:
            params["pageToken"] = page_token
        response = service.events().list(**params).execute()
        events.extend(response.get("items", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return events
