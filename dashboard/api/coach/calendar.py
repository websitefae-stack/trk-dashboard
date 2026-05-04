import frappe
from frappe import _
from frappe.utils import add_to_date, getdate, get_datetime, get_fullname

from dashboard.api.session_worker import calendar as sw_calendar


DASHBOARD_ADMIN_USERS = [
    "hq@theresilientkid.co.uk",
    "office@theresilientpeople.uk",
]


def _require_logged_in_user():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def _is_dashboard_admin():
    return (frappe.session.user or "").strip().lower() in {email.lower() for email in DASHBOARD_ADMIN_USERS}


def _get_current_coach_context(user):
    fullname = (get_fullname(user) or "").strip()

    context = {
        "user": user,
        "coach_name": None,
        "coach_label": fullname or user,
        "resolution_note": "",
        "is_dashboard_admin": _is_dashboard_admin(),
    }

    if context["is_dashboard_admin"]:
        context["coach_label"] = "Dashboard Admin"
        context["resolution_note"] = "Dashboard admin access."
        return context

    if not frappe.db.exists("DocType", "Coach"):
        context["resolution_note"] = "Could not find Coach DocType."
        return context

    meta = frappe.get_meta("Coach")
    fields = ["name"]

    label_fields = ["coach_name", "full_name", "employee_name", "user_full_name", "title", "name"]
    login_fields = ["user", "user_id", "email", "coach_email"]

    for fieldname in label_fields + login_fields:
        if meta.has_field(fieldname) and fieldname not in fields:
            fields.append(fieldname)

    for login_field in login_fields:
        if meta.has_field(login_field):
            row = frappe.db.get_value("Coach", {login_field: user}, fields, as_dict=True)
            if row:
                context["coach_name"] = row.get("name")
                context["coach_label"] = _get_label(row, label_fields)
                context["resolution_note"] = "Resolved logged-in user to Coach / " + row.get("name")
                return context

    for label_field in label_fields:
        if fullname and meta.has_field(label_field):
            row = frappe.db.get_value("Coach", {label_field: fullname}, fields, as_dict=True)
            if row:
                context["coach_name"] = row.get("name")
                context["coach_label"] = _get_label(row, label_fields)
                context["resolution_note"] = "Resolved logged-in user to Coach / " + row.get("name")
                return context

    context["resolution_note"] = "Could not resolve the logged-in user to a Coach record."
    return context


def _get_label(row, fields):
    for fieldname in fields:
        value = (row.get(fieldname) or "").strip()
        if value:
            return value
    return row.get("name") or ""


def _coach_can_view_client(client_row, coach_context):
    if coach_context.get("is_dashboard_admin"):
        return True

    coach_name = (coach_context.get("coach_name") or "").strip()
    if not coach_name:
        return False

    return client_row.get("primary_coach") == coach_name or client_row.get("attending_coach") == coach_name


def _get_client_rows_for_worker(session_worker):
    if not session_worker or not frappe.db.exists("DocType", "Client"):
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
    ]:
        if meta.has_field(fieldname) and fieldname not in fields:
            fields.append(fieldname)

    return frappe.get_all(
        "Client",
        fields=fields,
        filters={"session_worker": session_worker},
        order_by="full_name asc" if meta.has_field("full_name") else "modified desc",
        limit_page_length=1000,
        ignore_permissions=True,
    )


def _get_client_row(client):
    if not client or not frappe.db.exists("Client", client):
        return None

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

    return frappe.db.get_value("Client", client, fields, as_dict=True)


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


def _get_session_worker_label(worker):
    if not worker:
        return ""

    if not frappe.db.exists("DocType", "Session Worker"):
        return worker

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


def _get_session_worker_options(coach_context):
    if not frappe.db.exists("DocType", "Client"):
        return []

    client_meta = frappe.get_meta("Client")

    if not client_meta.has_field("session_worker"):
        return []

    filters = {"session_worker": ["is", "set"]}
    or_filters = None

    if not coach_context.get("is_dashboard_admin"):
        coach_name = coach_context.get("coach_name")
        if not coach_name:
            return []

        or_filters = []
        if client_meta.has_field("primary_coach"):
            or_filters.append(["Client", "primary_coach", "=", coach_name])
        if client_meta.has_field("attending_coach"):
            or_filters.append(["Client", "attending_coach", "=", coach_name])

        if not or_filters:
            return []

    rows = frappe.get_all(
        "Client",
        fields=["session_worker"],
        filters=filters,
        or_filters=or_filters,
        limit_page_length=1000,
        ignore_permissions=True,
    )

    worker_names = sorted({row.get("session_worker") for row in rows if row.get("session_worker")})

    return [
        {
            "value": worker,
            "label": _get_session_worker_label(worker),
        }
        for worker in worker_names
    ]


def _get_selected_session_worker(selected_worker, coach_context):
    options = _get_session_worker_options(coach_context)
    allowed = {row["value"] for row in options}

    if selected_worker and selected_worker in allowed:
        return selected_worker, options

    if options:
        return options[0]["value"], options

    return "", options


def _get_client_options_for_coach_worker(session_worker, coach_context):
    options = []

    for row in _get_client_rows_for_worker(session_worker):
        if not _coach_can_view_client(row, coach_context):
            continue

        options.append({
            "value": row.get("name"),
            "label": _get_client_display_from_row(row),
        })

    return options


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


def _get_coach_events(range_start_date, range_end_date, selected_worker, coach_context):
    if not selected_worker or not sw_calendar._event_has_field("custom_client"):
        return []

    client_rows = _get_client_rows_for_worker(selected_worker)
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
        limit_page_length=500,
        ignore_permissions=True,
    )

    events = []

    for row in rows:
        raw_status = sw_calendar._get_event_status(row)
        ui_status = sw_calendar._map_event_status_to_ui(raw_status)

        if ui_status == "Cancelled":
            continue

        custom_client = row.get("custom_client")
        client_row = client_map.get(custom_client)
        is_allowed = _coach_can_view_client(client_row or {}, coach_context)

        start_dt = get_datetime(row.get("starts_on"))
        end_dt = get_datetime(row.get("ends_on")) if row.get("ends_on") else None

        if not is_allowed:
            events.append({
                "id": row.get("name"),
                "name": row.get("name"),
                "title": "Unavailable",
                "client_name": "",
                "date": start_dt.strftime("%Y-%m-%d"),
                "start_time": start_dt.strftime("%H:%M"),
                "end_time": end_dt.strftime("%H:%M") if end_dt else start_dt.strftime("%H:%M"),
                "status": "Booked",
                "ui_status": "Booked",
                "type": "General",
                "billing_type": "",
                "travel_charged": 0,
                "travel_miles_one_way": 0,
                "return_trip_required": 0,
                "total_travel_miles": 0,
                "worker": _get_session_worker_label(selected_worker),
                "location": "",
                "notes": "",
                "record_url": "",
                "session_number": 0,
                "total_sessions": 0,
                "progress_text": "",
                "booking_warning": "This appointment belongs to another coach. Details are hidden.",
                "is_private": 1,
            })
            continue

        session_type = sw_calendar._get_effective_session_type(row)
        title = row.get("subject") or "Session"

        if custom_client:
            try:
                title = sw_calendar._get_client_display_name(custom_client) + " - " + session_type
            except Exception:
                pass

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
            "worker": _get_session_worker_label(selected_worker),
            "location": row.get("location") or "",
            "notes": row.get("description") or "",
            "record_url": f"/coach_db/calendar_details?event={row.get('name')}",
            "session_number": int(row.get("custom_session_number") or 0),
            "total_sessions": int(row.get("custom_total_sessions") or 0),
            "progress_text": row.get("custom_progress_text") or "",
            "booking_warning": row.get("custom_booking_warning") or "",
            "is_private": 0,
        })

    return events


@frappe.whitelist(allow_guest=False)
def get_calendar_bootstrap(week_start=None, view=None, date=None, selected_worker=None):
    _require_logged_in_user()
    coach_context = _get_current_coach_context(frappe.session.user)

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

    selected_worker, session_workers = _get_selected_session_worker(selected_worker, coach_context)

    return {
        "events": _get_coach_events(range_start_date, range_end_date, selected_worker, coach_context),
        "clients": _get_client_options_for_coach_worker(selected_worker, coach_context),
        "session_workers": session_workers,
        "selected_worker": selected_worker,
        "current_user": frappe.session.user,
        "current_user_fullname": get_fullname(frappe.session.user),
        "current_worker_name": selected_worker,
        "current_worker_label": _get_session_worker_label(selected_worker),
        "session_worker_doctype": "Session Worker",
        "resolution_note": coach_context.get("resolution_note") or "",
        "is_dashboard_admin": 1 if coach_context.get("is_dashboard_admin") else 0,
    }


@frappe.whitelist(allow_guest=False)
def get_event_details(event=None):
    _require_logged_in_user()
    coach_context = _get_current_coach_context(frappe.session.user)

    event_name = sw_calendar._coalesce_str("event", event)
    if not event_name:
        frappe.throw(_("Event is required."))

    event_doc = sw_calendar._get_event_doc(event_name)
    client = (event_doc.get("custom_client") or "").strip()
    client_row = _get_client_row(client)

    if not client_row or not _coach_can_view_client(client_row, coach_context):
        frappe.throw(_("This appointment belongs to another coach. Details are hidden."), frappe.PermissionError)

    start_dt = get_datetime(event_doc.get("starts_on")) if event_doc.get("starts_on") else None
    end_dt = get_datetime(event_doc.get("ends_on")) if event_doc.get("ends_on") else None

    raw_status = sw_calendar._get_event_status(event_doc)
    ui_status = sw_calendar._map_event_status_to_ui(raw_status)
    session_type = sw_calendar._get_effective_session_type(event_doc)

    return {
        "name": event_doc.get("name"),
        "client_name": client,
        "client_label": sw_calendar._get_client_display_name(client) if client else event_doc.get("subject") or "Session",
        "appointment_type": session_type,
        "status": raw_status,
        "ui_status": ui_status,
        "worker_label": _get_session_worker_label(client_row.get("session_worker")),
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
    coach_context = _get_current_coach_context(frappe.session.user)

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
    if not client_row or not _coach_can_view_client(client_row, coach_context):
        frappe.throw(_("You do not have permission to book this client."), frappe.PermissionError)

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
        "record_url": f"/coach_db/calendar_details?event={event.name}",
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
    coach_context = _get_current_coach_context(frappe.session.user)

    event_name = sw_calendar._coalesce_str("event", event)
    if not event_name:
        frappe.throw(_("Event is required."))

    event_doc = frappe.get_doc("Event", event_name)
    client = (event_doc.get("custom_client") or "").strip()
    client_row = _get_client_row(client)

    if not client_row or not _coach_can_view_client(client_row, coach_context):
        frappe.throw(_("You cannot edit this appointment because it belongs to another coach."), frappe.PermissionError)

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
        event_doc.appointment_status = sw_calendar._map_ui_status_to_event(status or "Booked")

    if sw_calendar._event_has_field("status"):
        event_doc.status = sw_calendar._map_ui_status_to_event(status or "Booked")

    if sw_calendar._event_has_field("location"):
        event_doc.location = location

    if sw_calendar._event_has_field("event_type"):
        event_doc.event_type = "Public"

    if sw_calendar._event_has_field("custom_travel_charged"):
        event_doc.custom_travel_charged = 1 if sw_calendar._to_int(travel_charged) else 0

    client_doc = frappe.get_doc("Client", client)
    client_travel = sw_calendar._get_client_travel_defaults(client_doc)

    if sw_calendar._event_has_field("custom_travel_miles_one_way"):
        event_doc.custom_travel_miles_one_way = float(client_travel.get("miles_one_way") or 0)

    if sw_calendar._event_has_field("custom_return_trip_required"):
        event_doc.custom_return_trip_required = 1

    if sw_calendar._event_has_field("custom_session_worker") and client_row.get("session_worker"):
        event_doc.custom_session_worker = client_row.get("session_worker")

    if sw_calendar._event_has_field("custom_total_travel_miles"):
        event_doc.custom_total_travel_miles = sw_calendar._get_effective_total_travel_miles(event_doc)

    client_label = sw_calendar._get_client_display_name(client)
    event_doc.subject = f"{client_label} - {session_type_value or 'Session'}"

    event_doc.save(ignore_permissions=True)

    return {
        "name": event_doc.name,
        "billing_type": event_doc.get("custom_billing_type") or "",
        "travel_charged": int(event_doc.get("custom_travel_charged") or 0),
        "travel_miles_one_way": float(event_doc.get("custom_travel_miles_one_way") or 0),
        "total_travel_miles": float(event_doc.get("custom_total_travel_miles") or 0),
    }


@frappe.whitelist(allow_guest=False)
def add_client_note(client=None, session_date=None, session_type=None, notes=None):
    _require_logged_in_user()
    coach_context = _get_current_coach_context(frappe.session.user)

    client = sw_calendar._coalesce_str("client", client)
    client_row = _get_client_row(client)

    if not client_row or not _coach_can_view_client(client_row, coach_context):
        frappe.throw(_("You cannot add notes for this client."), frappe.PermissionError)

    return sw_calendar.add_client_note(
        client=client,
        session_date=session_date,
        session_type=session_type,
        notes=notes,
    )
