import frappe
from frappe import _


@frappe.whitelist()
def get_calendar_bootstrap(week_start=None, view=None, date=None):
    """
    Bootstrap data for calendar
    """

    user = frappe.session.user

    # TODO: replace with your real logic
    # For now return empty structure so frontend loads

    return {
        "events": [],
        "week_start": week_start,
        "view": view,
        "date": date,
        "user": user,
    }


@frappe.whitelist()
def get_calendar_events(start=None, end=None):
    """
    Fetch events (placeholder)
    """

    return []


@frappe.whitelist()
def get_calendar_event_details(event_id=None):
    """
    Event details (placeholder)
    """

    return {
        "event_id": event_id,
        "title": "Sample Event",
        "description": "No data yet",
    }
