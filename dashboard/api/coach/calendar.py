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
    return frappe.session.user


def _is_dashboard_admin():
    user = (frappe.session.user or "").strip().lower()
    return user in {email.lower() for email in DASHBOARD_ADMIN_USERS}


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

    doctype = "Coach"
    if not frappe.db.exists("DocType", doctype):
        context["resolution_note"] = "Could not find Coach DocType."
        return context

    meta = frappe.get_meta(doctype)

    fields = ["name"]
    label_fields = ["coach_name", "full_name", "employee_name", "user_full_name", "title", "name"]
    login_fields = ["user", "user_id", "email", "coach_email"]

    for fieldname in label_fields + login_fields:
        if meta.has_field(fieldname) and fieldname not in fields:
            fields.append(fieldname)

    for login_field in login_fields:
        if meta.has_field(login_field):
            row = frappe.db.get_value(doctype, {login_field: user}, fields, as_dict=True)
            if row:
                context["coach_name"] = row.get("name")
                context["coach_label"] = _get_coach_label(row)
                context["resolution_note"] = "Resolved logged-in user to Coach / " + row.get("name")
                return context

    for label_field in label_fields:
        if fullname and meta.has_field(label_field):
            row = frappe.db.get_value(doctype, {label_field: fullname}, fields, as_dict=True)
            if row:
                context["coach_name"] = row.get("name")
                context["coach_label"] = _get_coach_label(row)
                context["resolution_note"] = "Resolved logged-in user to Coach / " + row.get("name")
                return context

    context["resolution_note"] = "Could not resolve the logged-in user to a Coach record."
    return context


def _get_coach_label(row):
    for fieldname in ["coach_name", "full_name", "employee_name", "user_full_name", "title", "name"]:
        value = (row.get(fieldname) or "").strip()
        if value:
            return value
    return ""


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
        if meta.has_field(fieldname):
            fields.append(fieldname)

    filters = {}
    if meta.has_field("session_worker"):
        filters["session_worker"] = session_worker

    return frappe.get_all(
        "Client",
        fields=fields,
        filters=filters,
        order_by="full_name asc" if meta.has_field("full_name") else "modified desc",
        limit_page_length=1000,
        ignore_permissions=True,
    )


def _get_client_display_from_row(row):
    for fieldname in ["full_name", "preferred_name", "name1", "name"]:
        value = (row.get(fieldname) or "").strip()
        if value:
            return value

    first = (row.get("name1") or "").strip()
    last = (row.get("last_name") or "").strip()
    full = " ".join([part for part in [first, last] if part]).strip()
    return full or row.get("name")


def _get_session_worker_options(coach_context):
    if not frappe.db.exists("DocType", "Client"):
        return []

    meta = frappe.get_meta("Client")
    if not meta.has_field("session_worker"):
        return []

    filters = {}

    if not coach_context.get("is_dashboard_admin"):
        coach_name = coach_context.get("coach_name")
        if not coach_name:
            return []

        filters = [
            ["Client", "session_worker", "is", "set"],
            [
                ["Client", "primary_coach", "=", coach_name],
                ["Client", "attending_coach", "=", coach_name],
            ],
        ]

    rows = frappe.get_all(
        "Client",
        fields=["session_worker"],
        filters=filters,
        limit_page_length=1000,
        ignore_permissions=True,
    )

    worker_names = sorted({row.get("session_worker") for row in rows if row.get("session_worker")})
    if not worker_names:
        return []

    worker_meta = frappe.get_meta("Session Worker") if frappe.db.exists("DocType", "Session Worker") else None
    label_fields = ["sw_name", "session_worker_name", "full_name", "employee_name", "user_full_name", "title"]

    options = []
    for worker in worker_names:
        label = worker

        if worker_meta:
            fields = ["name"] + [field for field in label_fields if worker_meta.has_field(field)]
            row = frappe.db.get_value("Session Worker", worker, fields, as_dict=True)
            if row:
                for fieldname in label_fields:
                    value = (row.get(fieldname) or "").strip()
                    if value:
                        label = value
                        break

        options.append({"value": worker, "label": label})

    return options


def _get_selected_session_worker(selected_worker, coach_context):
    options = _get_session_worker_options(coach_context)
    allowed = {row["value"] for row in options}

    if selected_worker and selected_worker in allowed:
        return selected_worker, options

    if options:
        return options[0]["value"], options

    return "", options


def _get_client_options_for_coach_worker(session_worker, coach_context):
    rows = _get_client_rows_for_worker(session_worker)

    options = []
    for row in rows:
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
    if not sw_calendar._event_has_field("custom_client"):
        return []

    client_rows = _get_client_rows_for_worker(selected_worker)
    client_map = {row.get("name"): row for row in client_rows if row.get("name")}

    if not client_map:
        return []

    filters = [
        ["Event", "starts_on", ">=", f"{range_start_date} 00:00:00"],
        ["Event", "starts_on", "<=", f"{range_end_date} 23:59:59"],
        ["Event", "custom_client", "in", list(client_map.keys())],
    ]

    rows = frappe.get_all(
        "Event",
        fields=_get_event_fields(),
        filters=filters,
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
                "type": "Unavailable",
                "billing_type": "",
                "travel_charged": 0,
                "travel_miles_one_way": 0,
                "return_trip_required": 0,
                "total_travel_miles": 0,
                "worker": selected_worker,
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
            "worker": selected_worker,
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
        "current_worker_label": selected_worker,
        "session_worker_doctype": "Session Worker",
        "resolution_note": coach_context.get("resolution_note") or "",
        "is_dashboard_admin": 1 if coach_context.get("is_dashboard_admin") else 0,
    }


@frappe.whitelist(allow_guest=False)
def create_booking(**kwargs):
    _require_logged_in_user()
    coach_context = _get_current_coach_context(frappe.session.user)

    client = sw_calendar._coalesce_str("client", kwargs.get("client"))
    if not client:
        frappe.throw(_("Please select a client."))

    client_rows = _get_client_rows_for_worker(frappe.db.get_value("Client", client, "session_worker"))
    client_map = {row.get("name"): row for row in client_rows}
    if not _coach_can_view_client(client_map.get(client) or {}, coach_context):
        frappe.throw(_("You do not have permission to book this client."), frappe.PermissionError)

    return sw_calendar.create_booking(**kwargs)


@frappe.whitelist(allow_guest=False)
def update_session(**kwargs):
    _require_logged_in_user()
    coach_context = _get_current_coach_context(frappe.session.user)

    event_name = sw_calendar._coalesce_str("event", kwargs.get("event"))
    if not event_name:
        frappe.throw(_("Event is required."))

    event_doc = sw_calendar._get_event_doc(event_name)
    client = (event_doc.get("custom_client") or "").strip()

    if not client:
        frappe.throw(_("This appointment is not linked to a client."), frappe.PermissionError)

    client_rows = _get_client_rows_for_worker(frappe.db.get_value("Client", client, "session_worker"))
    client_map = {row.get("name"): row for row in client_rows}

    if not _coach_can_view_client(client_map.get(client) or {}, coach_context):
        frappe.throw(_("You cannot edit this appointment because it belongs to another coach."), frappe.PermissionError)

    return sw_calendar.update_session(**kwargs)


@frappe.whitelist(allow_guest=False)
def add_client_note(**kwargs):
    _require_logged_in_user()
    coach_context = _get_current_coach_context(frappe.session.user)

    client = sw_calendar._coalesce_str("client", kwargs.get("client"))
    if not client:
        frappe.throw(_("Client is required."))

    client_rows = _get_client_rows_for_worker(frappe.db.get_value("Client", client, "session_worker"))
    client_map = {row.get("name"): row for row in client_rows}

    if not _coach_can_view_client(client_map.get(client) or {}, coach_context):
        frappe.throw(_("You cannot add notes for this client."), frappe.PermissionError)

    return sw_calendar.add_client_note(**kwargs)


@frappe.whitelist(allow_guest=False)
def get_event_details(event=None):
    _require_logged_in_user()
    coach_context = _get_current_coach_context(frappe.session.user)

    event_name = sw_calendar._coalesce_str("event", event)
    if not event_name:
        frappe.throw(_("Event is required."))

    event_doc = sw_calendar._get_event_doc(event_name)
    client = (event_doc.get("custom_client") or "").strip()

    if not client:
        frappe.throw(_("This appointment is not linked to a client."), frappe.PermissionError)

    client_rows = _get_client_rows_for_worker(frappe.db.get_value("Client", client, "session_worker"))
    client_map = {row.get("name"): row for row in client_rows}

    if not _coach_can_view_client(client_map.get(client) or {}, coach_context):
        frappe.throw(_("This appointment belongs to another coach. Details are hidden."), frappe.PermissionError)

    return sw_calendar.get_event_details(event=event_name)
