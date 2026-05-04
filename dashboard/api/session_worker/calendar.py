import frappe
from frappe import _
from frappe.utils import getdate


@frappe.whitelist()
def get_calendar_bootstrap(week_start=None, view=None, date=None):
    user = frappe.session.user

    # Get Session Worker linked to this user
    session_worker = frappe.db.get_value(
        "Session Worker",
        {"user": user},
        "name"
    )

    if not session_worker:
        return {
            "events": [],
            "clients": [],
        }

    # Get Sessions
    sessions = frappe.get_all(
        "Session",
        filters={
            "session_worker": session_worker
        },
        fields=[
            "name",
            "client",
            "start_datetime",
            "end_datetime",
            "status"
        ]
    )

    events = []

    for s in sessions:
        events.append({
            "id": s.name,
            "title": s.client or "Session",
            "start": s.start_datetime,
            "end": s.end_datetime,
            "status": s.status,
            "record_url": f"/session_worker_db/calendar_details?event={s.name}",
        })

    # Get Clients
    clients = frappe.get_all(
        "Client",
        fields=["name", "full_name"]
    )

    client_list = [
        {
            "value": c.name,
            "label": c.full_name or c.name
        }
        for c in clients
    ]

    return {
        "events": events,
        "clients": client_list,
    }


@frappe.whitelist()
def create_calendar_event(client, start, end):
    user = frappe.session.user

    session_worker = frappe.db.get_value(
        "Session Worker",
        {"user": user},
        "name"
    )

    doc = frappe.get_doc({
        "doctype": "Session",
        "session_worker": session_worker,
        "client": client,
        "start_datetime": start,
        "end_datetime": end,
        "status": "Scheduled"
    })

    doc.insert(ignore_permissions=True)

    return {
        "success": True,
        "event_id": doc.name
    }


@frappe.whitelist()
def get_calendar_event_details(event):
    doc = frappe.get_doc("Session", event)

    return {
        "name": doc.name,
        "client": doc.client,
        "start": doc.start_datetime,
        "end": doc.end_datetime,
        "status": doc.status,
    }
