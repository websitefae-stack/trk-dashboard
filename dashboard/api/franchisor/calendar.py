import frappe
from frappe import _
from frappe.utils import add_to_date, getdate, get_datetime, get_fullname

from dashboard.api.session_worker import calendar as sw_calendar


FRANCHISOR_ME_VALUE = "__franchisor_me__"
COACH_PREFIX = "__coach__:"
WORKER_PREFIX = "__worker__:"


def _require_logged_in_user():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def _get_label(row, fields):
    for fieldname in fields:
        value = (row.get(fieldname) or "").strip()
        if value:
            return value
    return row.get("name") or ""


def _get_current_user_label():
    return get_fullname(frappe.session.user) or frappe.session.user


def _get_client_base_fields():
    if not frappe.db.exists("DocType", "Client"):
        return []

    meta = frappe.get_meta("Client")
    fields = ["name"]

    for fieldname in [
        "session_worker",
        "primary_coach",
        "attending_coach",
        "full_name",
        "name1",
        "last_name",
        "preferred_name",
        "travel_charged",
        "travel_miles_one_way",
    ]:
        if meta.has_field(fieldname) and fieldname not in fields:
            fields.append(fieldname)

    return fields


def _get_client_row(client):
    if not client or not frappe.db.exists("Client", client):
        return None

    return frappe.db.get_value("Client", client, _get_client_base_fields(), as_dict=True)


def _get_all_client_rows():
    if not frappe.db.exists("DocType", "Client"):
        return []

    return frappe.get_all(
        "Client",
        fields=_get_client_base_fields(),
        order_by="full_name asc",
        limit_page_length=5000,
        ignore_permissions=True,
    )


def _get_client_rows_for_worker(worker):
    if not worker or not frappe.db.exists("DocType", "Client"):
        return []

    return frappe.get_all(
        "Client",
        fields=_get_client_base_fields(),
        filters={"session_worker": worker},
        order_by="full_name asc",
        limit_page_length=3000,
        ignore_permissions=True,
    )


def _get_client_rows_for_coach(coach):
    if not coach or not frappe.db.exists("DocType", "Client"):
        return []

    meta = frappe.get_meta("Client")
    or_filters = []

    if meta.has_field("primary_coach"):
        or_filters.append(["Client", "primary_coach", "=", coach])

    if meta.has_field("attending_coach"):
        or_filters.append(["Client", "attending_coach", "=", coach])

    if not or_filters:
        return []

    return frappe.get_all(
        "Client",
        fields=_get_client_base_fields(),
        or_filters=or_filters,
        order_by="full_name asc",
        limit_page_length=3000,
        ignore_permissions=True,
    )


def _get_client_display_from_row(row):
    if not row:
        return ""

    for fieldname in ["full_name", "preferred_name", "name1", "name"]:
        value = (row.get(fieldname) or "").strip()
        if value:
            return value

    first = (row.get("name1") or "").strip()
    last = (row.get("last_name") or "").strip()
    return " ".join([part for part in [first, last] if part]).strip() or row.get("name")


def _get_coach_label(coach):
    if not coach or not frappe.db.exists("DocType", "Coach"):
        return coach or ""

    meta = frappe.get_meta("Coach")
    label_fields = ["coach_name", "full_name", "employee_name", "user_full_name", "title", "name"]

    fields = ["name"]
    for fieldname in label_fields:
        if meta.has_field(fieldname) and fieldname not in fields:
            fields.append(fieldname)

    row = frappe.db.get_value("Coach", coach, fields, as_dict=True)
    if not row:
        return coach

    return _get_label(row, label_fields) or coach


def _get_session_worker_label(worker):
    if not worker or not frappe.db.exists("DocType", "Session Worker"):
        return worker or ""

    meta = frappe.get_meta("Session Worker")
    label_fields = ["sw_name", "session_worker_name", "full_name", "employee_name", "user_full_name", "title", "name"]

    fields = ["name"]
    for fieldname in label_fields:
        if meta.has_field(fieldname) and fieldname not in fields:
            fields.append(fieldname)

    row = frappe.db.get_value("Session Worker", worker, fields, as_dict=True)
    if not row:
        return worker

    return _get_label(row, label_fields) or worker


def _get_calendar_for_options():
    options = [
        {
            "value": FRANCHISOR_ME_VALUE,
            "label": "Me",
        }
    ]

    if frappe.db.exists("DocType", "Coach"):
        coach_meta = frappe.get_meta("Coach")
        coach_fields = ["name"]

        for fieldname in ["coach_name", "full_name", "employee_name", "user_full_name", "title"]:
            if coach_meta.has_field(fieldname):
                coach_fields.append(fieldname)

        coaches = frappe.get_all(
            "Coach",
            fields=coach_fields,
            order_by="name asc",
            limit_page_length=1000,
            ignore_permissions=True,
        )

        for coach in coaches:
            options.append({
                "value": COACH_PREFIX + coach.get("name"),
                "label": "Coach: " + _get_label(coach, ["coach_name", "full_name", "employee_name", "user_full_name", "title", "name"]),
            })

    if frappe.db.exists("DocType", "Session Worker"):
        worker_meta = frappe.get_meta("Session Worker")
        worker_fields = ["name"]

        for fieldname in ["sw_name", "session_worker_name", "full_name", "employee_name", "user_full_name", "title"]:
            if worker_meta.has_field(fieldname):
                worker_fields.append(fieldname)

        workers = frappe.get_all(
            "Session Worker",
            fields=worker_fields,
            order_by="name asc",
            limit_page_length=1000,
            ignore_permissions=True,
        )

        for worker in workers:
            options.append({
                "value": WORKER_PREFIX + worker.get("name"),
                "label": "Session Worker: " + _get_label(worker, ["sw_name", "session_worker_name", "full_name", "employee_name", "user_full_name", "title", "name"]),
            })

    return options


def _get_selected_calendar_for(selected_calendar_for):
    options = _get_calendar_for_options()
    allowed = {row["value"] for row in options}

    if selected_calendar_for and selected_calendar_for in allowed:
        return selected_calendar_for, options

    return FRANCHISOR_ME_VALUE, options


def _get_client_rows_for_calendar(selected_calendar_for):
    if selected_calendar_for == FRANCHISOR_ME_VALUE:
        return _get_all_client_rows()

    if selected_calendar_for.startswith(COACH_PREFIX):
        return _get_client_rows_for_coach(selected_calendar_for.replace(COACH_PREFIX, "", 1))

    if selected_calendar_for.startswith(WORKER_PREFIX):
        return _get_client_rows_for_worker(selected_calendar_for.replace(WORKER_PREFIX, "", 1))

    return []


def _get_current_calendar_label(selected_calendar_for):
    if selected_calendar_for == FRANCHISOR_ME_VALUE:
        return "Me"

    if selected_calendar_for.startswith(COACH_PREFIX):
        coach = selected_calendar_for.replace(COACH_PREFIX, "", 1)
        return "Coach: " + _get_coach_label(coach)

    if selected_calendar_for.startswith(WORKER_PREFIX):
        worker = selected_calendar_for.replace(WORKER_PREFIX, "", 1)
        return "Session Worker: " + _get_session_worker_label(worker)

    return "Calendar"


def _get_client_options_for_calendar(selected_calendar_for):
    rows = _get_client_rows_for_calendar(selected_calendar_for)

    return [
        {
            "value": row.get("name"),
            "label": _get_client_display_from_row(row),
        }
        for row in rows
        if row.get("name")
    ]


def _get_event_fields():
    fields = [
        "name",
        "subject",
        "starts_on",
        "ends_on",
        "location",
        "description",
        "owner",
        "custom_client",
        "custom_session_worker",
        "custom_appointment_status",
        "custom_appointment_type",
        "custom_billing_type",
        "custom_travel_charged",
        "custom_travel_miles_one_way",
        "custom_return_trip_required",
        "custom_total_travel_miles",
        "status",
        "event_type",
        "custom_session_number",
        "custom_total_sessions",
        "custom_progress_text",
        "custom_booking_warning",
    ]

    if sw_calendar._event_has_field("custom_session_type"):
        fields.append("custom_session_type")

    if sw_calendar._event_has_field("appointment_status"):
        fields.append("appointment_status")

    return fields


def _get_franchisor_events(range_start_date, range_end_date, selected_calendar_for):
    if not sw_calendar._event_has_field("custom_client"):
        return []

    client_rows = _get_client_rows_for_calendar(selected_calendar_for)
    client_map = {row.get("name"): row for row in client_rows if row.get("name")}

    if not client_map:
        return []

    rows = frappe.get_all(
        "Event",
        fields=_get_event_fields(),
        filters=[
            ["Event", "starts_on", ">=", f"{range_start_date} 00:00:00"],
            ["Event", "starts_on", "<=", f"{range_end_date} 23:59:59"],
            ["Event", "custom_client", "in", list(client_map.keys())],
        ],
        order_by="starts_on asc",
        limit_page_length=1000,
        ignore_permissions=True,
    )

    events = []

    for row in rows:
        raw_status = sw_calendar._get_event_status(row)
        ui_status = sw_calendar._map_event_status_to_ui(raw_status)

        if ui_status == "Cancelled":
            continue

        start_dt = get_datetime(row.get("starts_on"))
        end_dt = get_datetime(row.get("ends_on")) if row.get("ends_on") else None
        session_type = sw_calendar._get_effective_session_type(row)

        custom_client = row.get("custom_client")
        title = row.get("subject") or "Session"

        if custom_client:
            try:
                title = sw_calendar._get_client_display_name(custom_client) + " - " + session_type
            except Exception:
                pass

        worker_label = _get_current_calendar_label(selected_calendar_for)

        if custom_client and client_map.get(custom_client) and client_map.get(custom_client).get("session_worker"):
            worker_label = _get_session_worker_label(client_map.get(custom_client).get("session_worker"))

        events.append({
            "id": row.get("name"),
            "name": row.get("name"),
            "title": title,
            "client_name": custom_client or "",
            "date": start_dt.strftime("%Y-%m-%d"),
            "start_time": start_dt.strftime("%H:%M"),
            "end_time": end_dt.strftime("%H:%M") if end_dt else start_dt.strftime("%H:%M"),
            "status": raw_status,
            "ui_status": ui_status,
            "type": session_type,
            "billing_type": sw_calendar._get_effective_billing_type(row),
            "travel_charged": 1 if int(row.get("custom_travel_charged") or 0) else 0,
            "travel_miles_one_way": float(row.get("custom_travel_miles_one_way") or 0),
            "return_trip_required": int(row.get("custom_return_trip_required") or 0),
            "total_travel_miles": float(row.get("custom_total_travel_miles") or 0),
            "worker": worker_label,
            "location": row.get("location") or "",
            "notes": row.get("description") or "",
            "record_url": f"/franchisor_db/calendar_details?event={row.get('name')}",
            "session_number": int(row.get("custom_session_number") or 0),
            "total_sessions": int(row.get("custom_total_sessions") or 0),
            "progress_text": row.get("custom_progress_text") or "",
            "booking_warning": row.get("custom_booking_warning") or "",
            "is_private": 0,
        })

    return events


@frappe.whitelist(allow_guest=False)
def get_calendar_bootstrap(week_start=None, view=None, date=None, selected_worker=None, selected_calendar_for=None):
    _require_logged_in_user()

    selected_calendar_for = selected_calendar_for or selected_worker

    view = (view or "week").strip().lower()
    selected_date = getdate(date) if date else (getdate(week_start) if week_start else getdate())

    if view == "day":
        range_start_date = selected_date
        range_end_date = selected_date
    elif view == "month":
        range_start_date = selected_date.replace(day=1)
        range_end_date = add_to_date(range_start_date, months=1, days=-1)
    else:
        range_start_date = getdate(week_start) if week_start else selected_date
        range_end_date = add_to_date(range_start_date, days=6)

    selected_calendar_for, calendar_for_options = _get_selected_calendar_for(selected_calendar_for)

    return {
        "events": _get_franchisor_events(range_start_date, range_end_date, selected_calendar_for),
        "clients": _get_client_options_for_calendar(selected_calendar_for),
        "session_workers": calendar_for_options,
        "calendar_for_options": calendar_for_options,
        "selected_worker": selected_calendar_for,
        "selected_calendar_for": selected_calendar_for,
        "current_user": frappe.session.user,
        "current_user_fullname": get_fullname(frappe.session.user),
        "current_worker_name": selected_calendar_for,
        "current_worker_label": _get_current_calendar_label(selected_calendar_for),
        "session_worker_doctype": "Session Worker",
        "resolution_note": "",
        "is_dashboard_admin": 1,
    }


@frappe.whitelist(allow_guest=False)
def get_event_details(event=None):
    _require_logged_in_user()

    event_name = sw_calendar._coalesce_str("event", event)
    if not event_name:
        frappe.throw(_("Event is required."))

    event_doc = sw_calendar._get_event_doc(event_name)
    client = (event_doc.get("custom_client") or "").strip()
    client_row = _get_client_row(client)

    start_dt = get_datetime(event_doc.get("starts_on")) if event_doc.get("starts_on") else None
    end_dt = get_datetime(event_doc.get("ends_on")) if event_doc.get("ends_on") else None

    raw_status = sw_calendar._get_event_status(event_doc)
    ui_status = sw_calendar._map_event_status_to_ui(raw_status)
    session_type = sw_calendar._get_effective_session_type(event_doc)

    worker_label = "Me"
    if client_row and client_row.get("session_worker"):
        worker_label = _get_session_worker_label(client_row.get("session_worker"))

    return {
        "name": event_doc.get("name"),
        "client_name": client,
        "client_label": sw_calendar._get_client_display_name(client) if client else event_doc.get("subject") or "Session",
        "appointment_type": session_type,
        "status": raw_status,
        "ui_status": ui_status,
        "worker_label": worker_label,
        "display_date": start_dt.strftime("%A, %d %B %Y") if start_dt else "",
        "display_time": sw_calendar._format_time_range(start_dt, end_dt),
        "session_date": start_dt.strftime("%Y-%m-%d") if start_dt else "",
        "start_time": start_dt.strftime("%H:%M") if start_dt else "",
        "location": event_doc.get("location") or "",
        "billing_type": sw_calendar._get_effective_billing_type(event_doc),
        "travel_charged": 1 if int(event_doc.get("custom_travel_charged") or 0) else 0,
        "travel_miles_one_way": float(event_doc.get("custom_travel_miles_one_way") or 0),
        "total_travel_miles": float(event_doc.get("custom_total_travel_miles") or 0),
        "client_notes": sw_calendar._get_client_notes(client) if client else [],
        "session_number": int(event_doc.get("custom_session_number") or 0),
        "total_sessions": int(event_doc.get("custom_total_sessions") or 0),
        "progress_text": event_doc.get("custom_progress_text") or "",
        "booking_warning": event_doc.get("custom_booking_warning") or "",
    }


@frappe.whitelist(allow_guest=False)
def create_booking(
    client=None,
    client_name=None,
    booking_date=None,
    booking_time=None,
    duration_minutes=45,
    appointment_type="Therapy Session",
    location=None,
    notes=None,
    billing_type=None,
    travel_charged=None,
):
    _require_logged_in_user()

    client = sw_calendar._coalesce_str("client", client)
    client_name = sw_calendar._coalesce_str("client_name", client_name)
    booking_date = sw_calendar._coalesce_str("booking_date", booking_date)
    booking_time = sw_calendar._coalesce_str("booking_time", booking_time)
    appointment_type = sw_calendar._coalesce_str("appointment_type", appointment_type or "Therapy Session")
    location = sw_calendar._coalesce_str("location", location)
    notes = sw_calendar._coalesce_str("notes", notes)
    billing_type = sw_calendar._coalesce_str("billing_type", billing_type)
    travel_charged = sw_calendar._coalesce_raw("travel_charged", travel_charged)
    duration_minutes = sw_calendar._coalesce_raw("duration_minutes", duration_minutes)

    if not client:
        frappe.throw(_("Please select a client."))

    if not booking_date or not booking_time:
        frappe.throw(_("Please select a booking date and time."))

    client_row = _get_client_row(client)
    if not client_row:
        frappe.throw(_("Selected client was not found."))

    try:
        duration_minutes = int(duration_minutes or 45)
    except Exception:
        duration_minutes = 45

    if duration_minutes not in (30, 45, 60, 90):
        duration_minutes = 45

    start_dt = get_datetime(f"{booking_date} {booking_time}:00")
    end_dt = add_to_date(start_dt, minutes=duration_minutes)

    if not client_name:
        client_name = _get_client_display_from_row(client_row)

    event = frappe.new_doc("Event")
    event.subject = f"{client_name} - {appointment_type}"
    event.starts_on = start_dt
    event.ends_on = end_dt

    if sw_calendar._event_has_field("event_type"):
        event.event_type = "Public"

    if sw_calendar._event_has_field("custom_client"):
        event.custom_client = client

    sw_calendar._set_session_type(event, appointment_type)

    if sw_calendar._event_has_field("custom_billing_type"):
        event.custom_billing_type = sw_calendar._resolve_billing_type(
            appointment_type=appointment_type,
            selected_billing_type=billing_type,
        )

    client_travel = sw_calendar._get_client_travel_defaults(frappe.get_doc("Client", client))
    final_travel_charged = sw_calendar._to_int(travel_charged, default=int(client_travel.get("travel_charged") or 0))

    if sw_calendar._event_has_field("custom_travel_charged"):
        event.custom_travel_charged = 1 if final_travel_charged else 0

    if sw_calendar._event_has_field("custom_travel_miles_one_way"):
        event.custom_travel_miles_one_way = float(client_travel.get("miles_one_way") or 0)

    if sw_calendar._event_has_field("custom_return_trip_required"):
        event.custom_return_trip_required = 1

    if sw_calendar._event_has_field("custom_session_worker") and client_row.get("session_worker"):
        event.custom_session_worker = client_row.get("session_worker")

    if sw_calendar._event_has_field("custom_total_travel_miles"):
        event.custom_total_travel_miles = sw_calendar._get_effective_total_travel_miles(event)

    if sw_calendar._event_has_field("custom_appointment_status"):
        event.custom_appointment_status = "Scheduled"
    elif sw_calendar._event_has_field("appointment_status"):
        event.appointment_status = "Open"

    if sw_calendar._event_has_field("status"):
        event.status = "Open"

    if sw_calendar._event_has_field("location"):
        event.location = location

    if notes:
        event.description = notes

    event.insert(ignore_permissions=True)

    return {
        "name": event.name,
        "title": event.subject,
        "record_url": f"/franchisor_db/calendar_details?event={event.name}",
        "billing_type": event.get("custom_billing_type") or "",
        "travel_charged": int(event.get("custom_travel_charged") or 0),
        "travel_miles_one_way": float(event.get("custom_travel_miles_one_way") or 0),
        "total_travel_miles": float(event.get("custom_total_travel_miles") or 0),
    }


@frappe.whitelist(allow_guest=False)
def update_session(
    event=None,
    booking_date=None,
    booking_time=None,
    status=None,
    appointment_type=None,
    location=None,
    billing_type=None,
    travel_charged=None,
):
    _require_logged_in_user()

    event_name = sw_calendar._coalesce_str("event", event)
    if not event_name:
        frappe.throw(_("Event is required."))

    event_doc = frappe.get_doc("Event", event_name)
    client = (event_doc.get("custom_client") or "").strip()
    client_row = _get_client_row(client)

    booking_date = sw_calendar._coalesce_str("booking_date", booking_date)
    booking_time = sw_calendar._coalesce_str("booking_time", booking_time)
    status = sw_calendar._coalesce_str("status", status)
    appointment_type = sw_calendar._coalesce_str("appointment_type", appointment_type)
    location = sw_calendar._coalesce_str("location", location)
    billing_type = sw_calendar._coalesce_str("billing_type", billing_type)
    travel_charged = sw_calendar._coalesce_raw("travel_charged", travel_charged)

    if not booking_date or not booking_time:
        frappe.throw(_("Please select date and time."))

    old_start = get_datetime(event_doc.starts_on) if event_doc.starts_on else None
    old_end = get_datetime(event_doc.ends_on) if event_doc.ends_on else None
    duration_minutes = 45

    if old_start and old_end:
        duration_minutes = max(int((old_end - old_start).total_seconds() / 60), 15)

    new_start = get_datetime(f"{booking_date} {booking_time}:00")
    new_end = add_to_date(new_start, minutes=duration_minutes)

    event_doc.starts_on = new_start
    event_doc.ends_on = new_end

    session_type_value = appointment_type or sw_calendar._get_effective_session_type(event_doc)
    sw_calendar._set_session_type(event_doc, session_type_value)

    if sw_calendar._event_has_field("custom_billing_type"):
        event_doc.custom_billing_type = sw_calendar._resolve_billing_type(
            appointment_type=session_type_value,
            selected_billing_type=billing_type,
        )

    if sw_calendar._event_has_field("custom_appointment_status"):
        event_doc.custom_appointment_status = sw_calendar._map_ui_status_to_custom_status(status or "Booked")
    elif sw_calendar._event_has_field("appointment_status"):
        event_doc.appointment_status =
