import frappe
from frappe import _
from dashboard.api.shared.client_details import (
    add_client_note as shared_add_client_note,
    get_client_contacts as shared_get_client_contacts,
    get_client_notes as shared_get_client_notes,
    require_logged_in_user,
)
from trk_session_worker_dashboard.api.clients import (
    _ensure_client_access,
    get_session_worker_display_name,
)


EVENT_DOCTYPE = "Event"
EVENT_CLIENT_FIELD = "custom_client"


def get_session_worker_name():
    return get_session_worker_display_name()


def ensure_client_access(client_name):
    require_logged_in_user()
    _ensure_client_access(client_name)


@frappe.whitelist()
def get_client_contacts(client_name):
    ensure_client_access(client_name)

    return shared_get_client_contacts(
        client_name=client_name,
        contact_detail_base_url="/session_worker_db/contact_details",
    )


@frappe.whitelist()
def get_client_notes(client_name):
    ensure_client_access(client_name)
    return shared_get_client_notes(client_name)


@frappe.whitelist()
def add_client_note(client_name, note_text, session_date=None, session_type=None):
    ensure_client_access(client_name)

    return shared_add_client_note(
        client_name=client_name,
        note_text=note_text,
        session_date=session_date,
        session_type=session_type,
    )


def is_cancelled_status(status):
    return (status or "").strip().lower() in {
        "cancelled",
        "canceled",
        "cancelled by client",
        "cancelled by coach",
        "cancelled by session worker",
    }


def get_effective_event_session_type(event_row):
    value = (event_row.get("custom_session_type") or "").strip()

    if value:
        return value

    template_name = (event_row.get("custom_appointment_type") or "").strip()

    if template_name and frappe.db.exists("Appointment Template", template_name):
        template_doc = frappe.get_doc("Appointment Template", template_name)

        for fieldname in ["appointment_type", "title", "template_name", "name"]:
            template_value = (template_doc.get(fieldname) or "").strip()
            if template_value:
                return template_value

    return "General"


def get_event_status(event_row):
    for fieldname in [
        "custom_appointment_status",
        "appointment_status",
        "status",
    ]:
        value = event_row.get(fieldname)
        if value:
            return value

    return "Open"


def map_event_status_to_ui(raw_status):
    if is_cancelled_status(raw_status):
        return "Cancelled"

    mapping = {
        "Scheduled": "Booked",
        "Open": "Booked",
        "Attended": "Attended",
        "Completed": "Attended",
        "No Show": "No Show",
        "Closed": "No Show",
    }

    return mapping.get(raw_status, raw_status or "Booked")


@frappe.whitelist()
def get_client_appointments(client_name):
    ensure_client_access(client_name)

    if not frappe.db.exists("DocType", EVENT_DOCTYPE):
        return []

    event_meta = frappe.get_meta(EVENT_DOCTYPE)

    if not event_meta.has_field(EVENT_CLIENT_FIELD):
        return []

    fields = [
        "name",
        "subject",
        "starts_on",
        "ends_on",
        "location",
        "status",
    ]

    optional_fields = [
        "custom_client",
        "custom_session_type",
        "custom_appointment_type",
        "custom_appointment_status",
        "custom_billing_type",
        "custom_travel_charged",
        "appointment_status",
    ]

    for fieldname in optional_fields:
        if event_meta.has_field(fieldname):
            fields.append(fieldname)

    rows = frappe.get_all(
        EVENT_DOCTYPE,
        filters={EVENT_CLIENT_FIELD: client_name},
        fields=fields,
        order_by="starts_on desc",
        limit_page_length=500,
    )

    result = []

    for row in rows:
        raw_status = get_event_status(row)

        if is_cancelled_status(raw_status):
            continue

        starts_on = frappe.utils.get_datetime(row.get("starts_on")) if row.get("starts_on") else None
        ends_on = frappe.utils.get_datetime(row.get("ends_on")) if row.get("ends_on") else None

        display_date = starts_on.strftime("%Y-%m-%d") if starts_on else ""
        start_time = starts_on.strftime("%H:%M") if starts_on else ""
        end_time = ends_on.strftime("%H:%M") if ends_on else ""

        display_time = f"{start_time} - {end_time}" if start_time and end_time else start_time

        result.append(
            {
                "name": row.get("name"),
                "subject": row.get("subject") or "",
                "appointment_type": get_effective_event_session_type(row),
                "status": raw_status,
                "ui_status": map_event_status_to_ui(raw_status),
                "date": display_date,
                "time": display_time,
                "location": row.get("location") or "",
                "record_url": f"/session_worker_db/calendar_details?event={row.get('name')}",
            }
        )

    return result


def get_client_for_context(client_name):
    ensure_client_access(client_name)

    if not frappe.db.exists("Client", client_name):
        frappe.throw(_("Client not found."))

    return frappe.get_doc("Client", client_name)
