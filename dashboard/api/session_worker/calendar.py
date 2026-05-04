import frappe
from frappe import _
from frappe.utils import add_to_date, getdate, get_datetime, get_fullname


SESSION_WORKER_DOCTYPES = [
    "Session Worker",
]

DASHBOARD_ADMIN_USERS = [
    "hq@theresilientkid.co.uk",
    "office@theresilientpeople.uk",
]

FREE_TRAVEL_MILES_ONE_WAY = 10
TRAVEL_EXCLUDED_SESSION_TYPES = ["Parent Check-In"]


@frappe.whitelist(allow_guest=False)
def get_calendar_bootstrap(week_start=None, view=None, date=None):
    _require_logged_in_user()
    worker_context = _get_current_session_worker_context(frappe.session.user)

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

    clients = _get_client_options(worker_context)
    allowed_client_names = {row["value"] for row in clients}

    return {
        "events": _get_week_events(range_start_date, range_end_date, allowed_client_names, worker_context),
        "clients": clients,
        "current_user": frappe.session.user,
        "current_user_fullname": get_fullname(frappe.session.user),
        "current_worker_name": worker_context.get("worker_name") or "",
        "current_worker_label": worker_context.get("worker_label") or "",
        "session_worker_doctype": worker_context.get("worker_doctype") or "",
        "resolution_note": worker_context.get("resolution_note") or "",
        "is_dashboard_admin": 1 if worker_context.get("is_dashboard_admin") else 0,
    }


@frappe.whitelist(allow_guest=False)
def get_event_details(event=None):
    _require_logged_in_user()
    worker_context = _get_current_session_worker_context(frappe.session.user)

    event_name = _coalesce_str("event", event)
    if not event_name:
        frappe.throw(_("Event is required."))

    event_doc = _get_event_doc(event_name)
    custom_client = (event_doc.get("custom_client") or "").strip()

    if custom_client and not _client_belongs_to_session_worker(custom_client, worker_context):
        frappe.throw(_("You do not have permission to view this session."), frappe.PermissionError)

    start_dt = get_datetime(event_doc.get("starts_on")) if event_doc.get("starts_on") else None
    end_dt = get_datetime(event_doc.get("ends_on")) if event_doc.get("ends_on") else None

    client_label = ""
    if custom_client:
        client_label = _get_client_display_name(custom_client)

    raw_status = _get_event_status(event_doc)
    ui_status = _map_event_status_to_ui(raw_status)
    session_type = _get_effective_session_type(event_doc)
    final_billing_type = _get_effective_billing_type(event_doc)

    return {
        "name": event_doc.get("name"),
        "client_name": custom_client,
        "client_label": client_label or event_doc.get("subject") or "Session",
        "appointment_type": session_type,
        "status": raw_status,
        "ui_status": ui_status,
        "worker_label": worker_context.get("worker_label") or "",
        "display_date": start_dt.strftime("%A, %d %B %Y") if start_dt else "",
        "display_time": _format_time_range(start_dt, end_dt),
        "session_date": start_dt.strftime("%Y-%m-%d") if start_dt else "",
        "start_time": start_dt.strftime("%H:%M") if start_dt else "",
        "location": event_doc.get("location") or "",
        "billing_type": final_billing_type,
        "travel_charged": 1 if int(event_doc.get("custom_travel_charged") or 0) else 0,
        "travel_miles_one_way": float(event_doc.get("custom_travel_miles_one_way") or 0),
        "total_travel_miles": float(event_doc.get("custom_total_travel_miles") or 0),
        "client_notes": _get_client_notes(custom_client) if custom_client else [],
        "session_number": int(event_doc.get("custom_session_number") or 0),
        "total_sessions": int(event_doc.get("custom_total_sessions") or 0),
        "progress_text": event_doc.get("custom_progress_text") or "",
        "booking_warning": event_doc.get("custom_booking_warning") or "",
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
    worker_context = _get_current_session_worker_context(frappe.session.user)

    event_name = _coalesce_str("event", event)
    if not event_name:
        frappe.throw(_("Event is required."))

    booking_date = _coalesce_str("booking_date", booking_date)
    booking_time = _coalesce_str("booking_time", booking_time)
    status = _coalesce_str("status", status)
    appointment_type = _coalesce_str("appointment_type", appointment_type)
    location = _coalesce_str("location", location)
    billing_type = _coalesce_str("billing_type", billing_type)
    travel_charged = _coalesce_raw("travel_charged", travel_charged)

    if not booking_date or not booking_time:
        frappe.throw(_("Please select date and time."))

    event_doc = frappe.get_doc("Event", event_name)
    custom_client = (event_doc.get("custom_client") or "").strip()

    if custom_client and not _client_belongs_to_session_worker(custom_client, worker_context):
        frappe.throw(_("You do not have permission to update this session."), frappe.PermissionError)

    old_start = get_datetime(event_doc.starts_on) if event_doc.starts_on else None
    old_end = get_datetime(event_doc.ends_on) if event_doc.ends_on else None

    duration_minutes = 45
    if old_start and old_end:
        duration_minutes = max(int((old_end - old_start).total_seconds() / 60), 15)

    new_start = get_datetime(f"{booking_date} {booking_time}:00")
    new_end = add_to_date(new_start, minutes=duration_minutes)

    event_doc.starts_on = new_start
    event_doc.ends_on = new_end

    session_type_value = appointment_type or _get_effective_session_type(event_doc)
    _set_session_type(event_doc, session_type_value)

    if _event_has_field("custom_billing_type"):
        event_doc.custom_billing_type = _resolve_billing_type(
            appointment_type=session_type_value,
            selected_billing_type=billing_type,
        )

    if _event_has_field("custom_appointment_status"):
        event_doc.custom_appointment_status = _map_ui_status_to_custom_status(status or "Booked")
    elif _event_has_field("appointment_status"):
        event_doc.appointment_status = _map_ui_status_to_event(status or "Booked")

    if _event_has_field("status"):
        event_doc.status = _map_ui_status_to_event(status or "Booked")

    if _event_has_field("location"):
        event_doc.location = location

    if _event_has_field("event_type"):
        event_doc.event_type = "Public"

    if _event_has_field("custom_travel_charged"):
        event_doc.custom_travel_charged = 1 if _to_int(travel_charged) else 0

    if custom_client and frappe.db.exists("Client", custom_client):
        client_doc = frappe.get_doc("Client", custom_client)
        client_travel = _get_client_travel_defaults(client_doc)

        if _event_has_field("custom_travel_miles_one_way"):
            event_doc.custom_travel_miles_one_way = float(client_travel.get("miles_one_way") or 0)

        if _event_has_field("custom_return_trip_required"):
            event_doc.custom_return_trip_required = 1

        if _event_has_field("custom_session_worker") and client_doc.get("session_worker"):
            event_doc.custom_session_worker = client_doc.get("session_worker")

    if _event_has_field("custom_total_travel_miles"):
        event_doc.custom_total_travel_miles = _get_effective_total_travel_miles(event_doc)

    if custom_client:
        client_label = _get_client_display_name(custom_client)
        final_type = session_type_value or "Session"
        event_doc.subject = f"{client_label} - {final_type}"

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
    worker_context = _get_current_session_worker_context(frappe.session.user)

    client = _coalesce_str("client", client)
    session_type = _coalesce_str("session_type", session_type)
    notes = _coalesce_str("notes", notes)
    raw_session_date = _coalesce_raw("session_date", session_date)

    if not client:
        frappe.throw(_("Client is required."))

    if not notes:
        frappe.throw(_("Please enter a note."))

    if not frappe.db.exists("Client", client):
        frappe.throw(_("Selected client was not found."))

    if not _client_belongs_to_session_worker(client, worker_context):
        frappe.throw(_("You do not have permission to add notes for this client."), frappe.PermissionError)

    parentfield = _get_client_notes_parentfield()
    if not parentfield:
        frappe.throw(_("Could not find the Notes child table field on Client."))

    if not raw_session_date:
        raw_session_date = getdate()

    if not session_type:
        session_type = "Other"

    client_doc = frappe.get_doc("Client", client)
    client_doc.append(parentfield, {
        "doctype": "Notes",
        "client": client,
        "session_date": raw_session_date,
        "session_type": session_type,
        "notes": notes,
    })
    client_doc.save(ignore_permissions=True)

    return {
        "ok": True,
        "client_notes": _get_client_notes(client),
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
    worker_context = _get_current_session_worker_context(frappe.session.user)

    client = _coalesce_str("client", client)
    client_name = _coalesce_str("client_name", client_name)
    booking_date = _coalesce_str("booking_date", booking_date)
    booking_time = _coalesce_str("booking_time", booking_time)
    appointment_type = _coalesce_str("appointment_type", appointment_type or "Therapy Session")
    location = _coalesce_str("location", location)
    notes = _coalesce_str("notes", notes)
    billing_type = _coalesce_str("billing_type", billing_type)
    travel_charged = _coalesce_raw("travel_charged", travel_charged)
    duration_minutes = _coalesce_raw("duration_minutes", duration_minutes)

    if not client:
        frappe.throw(_("Please select a client."))

    if not booking_date or not booking_time:
        frappe.throw(_("Please select a booking date and time."))

    if not frappe.db.exists("Client", client):
        frappe.throw(_("Selected client was not found."))

    if not _client_belongs_to_session_worker(client, worker_context):
        frappe.throw(_("This client is not assigned to the logged-in session worker."))

    try:
        duration_minutes = int(duration_minutes or 45)
    except Exception:
        duration_minutes = 45

    if duration_minutes not in (30, 45, 60, 90):
        duration_minutes = 45

    start_dt = get_datetime(f"{booking_date} {booking_time}:00")
    end_dt = add_to_date(start_dt, minutes=duration_minutes)

    if not client_name:
        client_name = _get_client_display_name(client)

    subject = f"{client_name} - {appointment_type}"

    event = frappe.new_doc("Event")
    event.subject = subject
    event.starts_on = start_dt
    event.ends_on = end_dt

    if _event_has_field("event_type"):
        event.event_type = "Public"

    if _event_has_field("custom_client"):
        event.custom_client = client

    _set_session_type(event, appointment_type)

    if _event_has_field("custom_billing_type"):
        event.custom_billing_type = _resolve_billing_type(
            appointment_type=appointment_type,
            selected_billing_type=billing_type,
        )

    default_travel_charged = 0
    default_travel_miles_one_way = 0.0
    default_session_worker = ""

    if frappe.db.exists("Client", client):
        client_doc = frappe.get_doc("Client", client)
        client_travel = _get_client_travel_defaults(client_doc)
        default_travel_charged = int(client_travel.get("travel_charged") or 0)
        default_travel_miles_one_way = float(client_travel.get("miles_one_way") or 0)
        default_session_worker = client_doc.get("session_worker") or ""

    final_travel_charged = _to_int(travel_charged, default=default_travel_charged)

    if _event_has_field("custom_travel_charged"):
        event.custom_travel_charged = 1 if final_travel_charged else 0

    if _event_has_field("custom_travel_miles_one_way"):
        event.custom_travel_miles_one_way = default_travel_miles_one_way

    if _event_has_field("custom_return_trip_required"):
        event.custom_return_trip_required = 1

    if _event_has_field("custom_total_travel_miles"):
        event.custom_total_travel_miles = _get_effective_total_travel_miles(event)

    if _event_has_field("custom_session_worker") and default_session_worker:
        event.custom_session_worker = default_session_worker

    if _event_has_field("custom_appointment_status"):
        event.custom_appointment_status = "Scheduled"
    elif _event_has_field("appointment_status"):
        event.appointment_status = "Open"

    if _event_has_field("status"):
        event.status = "Open"

    if _event_has_field("location"):
        event.location = location

    if notes:
        event.description = notes

    event.insert(ignore_permissions=True)

    return {
        "name": event.name,
        "title": subject,
        "record_url": f"/session_worker_db/calendar_details?event={event.name}",
        "billing_type": event.get("custom_billing_type") or "",
        "travel_charged": int(event.get("custom_travel_charged") or 0),
        "travel_miles_one_way": float(event.get("custom_travel_miles_one_way") or 0),
        "total_travel_miles": float(event.get("custom_total_travel_miles") or 0),
    }


def _require_logged_in_user():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)
    return frappe.session.user


def _is_dashboard_admin():
    user = (frappe.session.user or "").strip().lower()
    return user in {email.lower() for email in DASHBOARD_ADMIN_USERS}


def _get_current_session_worker_context(user):
    fullname = (get_fullname(user) or "").strip()

    context = {
        "user": user,
        "worker_doctype": None,
        "worker_name": None,
        "worker_label": None,
        "resolution_note": "",
        "is_dashboard_admin": _is_dashboard_admin(),
    }

    if context["is_dashboard_admin"]:
        context["worker_label"] = "Dashboard Admin"
        context["resolution_note"] = "Dashboard admin access: showing all session-worker calendar data."
        return context

    found = _find_session_worker_for_user(user, fullname)
    if found:
        context["worker_doctype"] = found["doctype"]
        context["worker_name"] = found["name"]
        context["worker_label"] = found["label"]
        context["resolution_note"] = "Resolved logged-in user to " + found["doctype"] + " / " + found["name"]
        return context

    context["worker_label"] = fullname or user
    context["resolution_note"] = "Could not resolve a Session Worker record from the logged-in user. Client dropdown will stay empty until the portal user matches a Session Worker document."
    return context


def _find_session_worker_for_user(user, fullname):
    doctype = "Session Worker"
    if not frappe.db.exists("DocType", doctype):
        return None

    meta = frappe.get_meta(doctype)
    fields = ["name"]

    label_fields = ["session_worker_name", "full_name", "employee_name", "user_full_name", "title", "sw_name"]
    login_fields = ["user", "user_id", "email", "session_worker_email"]

    for fieldname in label_fields + login_fields:
        if meta.has_field(fieldname) and fieldname not in fields:
            fields.append(fieldname)

    for login_field in login_fields:
        if meta.has_field(login_field):
            row = frappe.db.get_value(doctype, {login_field: user}, fields, as_dict=True)
            if row:
                return {
                    "doctype": doctype,
                    "name": row.get("name"),
                    "label": _get_session_worker_label(row),
                }

    for label_field in label_fields:
        if fullname and meta.has_field(label_field):
            row = frappe.db.get_value(doctype, {label_field: fullname}, fields, as_dict=True)
            if row:
                return {
                    "doctype": doctype,
                    "name": row.get("name"),
                    "label": _get_session_worker_label(row),
                }

    return None


def _get_session_worker_label(row):
    for fieldname in ["sw_name", "session_worker_name", "full_name", "employee_name", "user_full_name", "title", "name"]:
        value = (row.get(fieldname) or "").strip()
        if value:
            return value
    return ""


def _event_has_field(fieldname):
    if frappe.db.exists("DocField", {"parent": "Event", "fieldname": fieldname}):
        return True

    if frappe.db.exists("Custom Field", {"dt": "Event", "fieldname": fieldname}):
        return True

    return False


def _set_session_type(doc, value):
    if _event_has_field("custom_session_type"):
        doc.custom_session_type = value
        return

    if _event_has_field("custom_appointment_type"):
        template_name = _find_appointment_template_name(value)
        doc.custom_appointment_type = template_name or ""
        return


def _find_appointment_template_name(label):
    if not label or not frappe.db.exists("DocType", "Appointment Template"):
        return ""

    if frappe.db.exists("Appointment Template", label):
        return label

    meta = frappe.get_meta("Appointment Template")
    candidate_fields = ["appointment_type", "title", "template_name"]

    for fieldname in candidate_fields:
        if meta.has_field(fieldname):
            row = frappe.db.get_value("Appointment Template", {fieldname: label}, "name")
            if row:
                return row

    return ""


def _get_effective_session_type(event_doc):
    value = (event_doc.get("custom_session_type") or "").strip()
    if value:
        return value

    template_name = (event_doc.get("custom_appointment_type") or "").strip()
    if template_name and frappe.db.exists("Appointment Template", template_name):
        template_doc = frappe.get_doc("Appointment Template", template_name)

        for fieldname in ["appointment_type", "title", "template_name", "name"]:
            template_value = (template_doc.get(fieldname) or "").strip()
            if template_value:
                return template_value

    return "General"


def _get_event_doc(event_name):
    fields = [
        "name",
        "subject",
        "starts_on",
        "ends_on",
        "location",
        "description",
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

    if _event_has_field("custom_session_type"):
        fields.append("custom_session_type")

    if _event_has_field("appointment_status"):
        fields.append("appointment_status")

    doc = frappe.db.get_value("Event", {"name": event_name}, fields, as_dict=True)
    if not doc:
        frappe.throw(_("Session record not found."))
    return doc


def _get_event_status(event_doc):
    if event_doc.get("custom_appointment_status"):
        return (event_doc.get("custom_appointment_status") or "Scheduled").strip()

    if event_doc.get("appointment_status"):
        return (event_doc.get("appointment_status") or "Open").strip()

    if event_doc.get("status"):
        return (event_doc.get("status") or "Open").strip()

    return "Open"


def _map_event_status_to_ui(raw_status):
    mapping = {
        "Scheduled": "Booked",
        "Open": "Booked",
        "Attended": "Attended",
        "Completed": "Attended",
        "Cancelled": "Cancelled",
        "No Show": "No Show",
        "Closed": "No Show",
    }
    return mapping.get(raw_status, "Booked")


def _map_ui_status_to_custom_status(ui_status):
    mapping = {
        "Booked": "Scheduled",
        "Attended": "Attended",
        "Cancelled": "Cancelled",
        "No Show": "No Show",
    }
    return mapping.get(ui_status, "Scheduled")


def _map_ui_status_to_event(ui_status):
    mapping = {
        "Booked": "Open",
        "Attended": "Completed",
        "Cancelled": "Cancelled",
        "No Show": "Closed",
    }
    return mapping.get(ui_status, "Open")


def _resolve_billing_type(appointment_type, selected_billing_type=""):
    appointment_type = (appointment_type or "").strip()
    selected_billing_type = (selected_billing_type or "").strip()

    if appointment_type == "General":
        return selected_billing_type or "Non-Billable"

    return "One to One"


def _get_effective_billing_type(row):
    billing_type = (row.get("custom_billing_type") or "").strip()
    if billing_type:
        return billing_type
    return _resolve_billing_type(_get_effective_session_type(row), "")


def _to_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return int(default or 0)


def _get_doc_value_by_candidates(doc, candidates, default=None):
    for fieldname in candidates:
        try:
            value = doc.get(fieldname)
        except Exception:
            value = None
        if value not in (None, ""):
            return value
    return default


def _get_client_travel_defaults(client_doc):
    travel_charged = _get_doc_value_by_candidates(
        client_doc,
        ["travel_charged", "custom_travel_charged", "is_travel_charged"],
        default=0,
    )

    miles_one_way = _get_doc_value_by_candidates(
        client_doc,
        ["travel_miles_one_way", "custom_travel_miles_one_way"],
        default=0,
    )

    return {
        "travel_charged": 1 if _to_int(travel_charged) else 0,
        "miles_one_way": float(miles_one_way or 0),
    }


def _get_effective_total_travel_miles(event_doc):
    session_type = (_get_effective_session_type(event_doc) or "").strip()

    if session_type in TRAVEL_EXCLUDED_SESSION_TYPES:
        return 0

    travel_enabled = int(event_doc.get("custom_travel_charged") or 0)
    if not travel_enabled:
        return 0

    one_way = float(event_doc.get("custom_travel_miles_one_way") or 0)
    return_trip = int(event_doc.get("custom_return_trip_required") or 0)

    chargeable_one_way = max(one_way - FREE_TRAVEL_MILES_ONE_WAY, 0)

    return chargeable_one_way * (2 if return_trip else 1)


def _get_request_payload():
    payload = {}
    try:
        if getattr(frappe, "request", None):
            payload = frappe.request.get_json(silent=True) or {}
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _coalesce_raw(fieldname, explicit_value=None):
    if explicit_value not in (None, ""):
        return explicit_value

    payload = _get_request_payload()
    if fieldname in payload and payload.get(fieldname) not in (None, ""):
        return payload.get(fieldname)

    form_value = frappe.form_dict.get(fieldname)
    if form_value not in (None, ""):
        return form_value

    return explicit_value


def _coalesce_str(fieldname, explicit_value=None):
    value = _coalesce_raw(fieldname, explicit_value)
    return (value or "").strip() if isinstance(value, str) else (str(value).strip() if value not in (None, "") else "")


def _client_belongs_to_session_worker(client_name, worker_context):
    if not client_name or not frappe.db.exists("Client", client_name):
        return False

    if worker_context.get("is_dashboard_admin"):
        return True

    worker_name = (worker_context.get("worker_name") or "").strip()
    if not worker_name:
        return False

    client_meta = frappe.get_meta("Client")
    if not client_meta.has_field("session_worker"):
        return False

    linked_worker = (frappe.db.get_value("Client", client_name, "session_worker") or "").strip()
    return linked_worker == worker_name


def _get_client_options(worker_context):
    if not frappe.db.exists("DocType", "Client"):
        return []

    client_meta = frappe.get_meta("Client")
    if not client_meta.has_field("session_worker"):
        return []

    fields = ["name", "session_worker"]
    if client_meta.has_field("full_name"):
        fields.append("full_name")
    if client_meta.has_field("first_name"):
        fields.append("first_name")
    if client_meta.has_field("last_name"):
        fields.append("last_name")

    if client_meta.has_field("full_name"):
        order_by = "full_name asc"
    elif client_meta.has_field("first_name"):
        order_by = "first_name asc"
    else:
        order_by = "modified desc"

    filters = {}
    if not worker_context.get("is_dashboard_admin"):
        worker_name = (worker_context.get("worker_name") or "").strip()
        if not worker_name:
            return []
        filters["session_worker"] = worker_name

    rows = frappe.get_all(
        "Client",
        fields=fields,
        filters=filters,
        order_by=order_by,
        limit_page_length=1000,
    )
    return [{"value": row.get("name"), "label": _build_client_label(row)} for row in rows]


def _get_client_notes_parentfield():
    if not frappe.db.exists("DocType", "Client"):
        return None

    meta = frappe.get_meta("Client")
    for field in meta.fields:
        if field.fieldtype == "Table" and field.options == "Notes":
            return field.fieldname
    return None


def _get_client_notes(client_name):
    if not client_name or not frappe.db.exists("Client", client_name):
        return []

    parentfield = _get_client_notes_parentfield()
    if not parentfield:
        return []

    client_doc = frappe.get_doc("Client", client_name)
    rows = client_doc.get(parentfield) or []

    notes = []
    for row in rows:
        note_owner = row.get("owner") or ""
        note_user_name = get_fullname(note_owner) if note_owner else ""

        notes.append({
            "name": row.name,
            "client": row.get("client") or client_name,
            "session_date": row.get("session_date").strftime("%Y-%m-%d") if row.get("session_date") else "",
            "session_type": row.get("session_type") or "",
            "notes": row.get("notes") or "",
            "note_user": note_owner,
            "note_user_name": note_user_name or note_owner,
            "idx": row.get("idx") or 0,
        })

    notes.sort(key=lambda d: ((d.get("session_date") or ""), d.get("idx") or 0), reverse=True)
    return notes


def _get_week_events(week_start_date, week_end_date, allowed_client_names, worker_context):
    if not _event_has_field("custom_client"):
        return []

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

    if _event_has_field("custom_session_type"):
        fields.append("custom_session_type")

    if _event_has_field("appointment_status"):
        fields.append("appointment_status")

    filters = [
        ["Event", "starts_on", ">=", f"{week_start_date} 00:00:00"],
        ["Event", "starts_on", "<=", f"{week_end_date} 23:59:59"],
    ]

    if not worker_context.get("is_dashboard_admin"):
        if not allowed_client_names:
            return []
        filters.append(["Event", "custom_client", "in", list(allowed_client_names)])

    rows = frappe.get_all(
        "Event",
        fields=fields,
        filters=filters,
        order_by="starts_on asc",
        limit_page_length=300,
    )

    events = []

    for row in rows:
        raw_status = _get_event_status(row)
        ui_status = _map_event_status_to_ui(raw_status)

        if ui_status == "Cancelled":
            continue

        start_dt = get_datetime(row.get("starts_on"))
        end_dt = get_datetime(row.get("ends_on")) if row.get("ends_on") else None
        session_type = _get_effective_session_type(row)

        title = row.get("subject") or "Session"
        custom_client = row.get("custom_client")

        if custom_client:
            try:
                title = _get_client_display_name(custom_client) + " - " + session_type
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
            "billing_type": _get_effective_billing_type(row),
            "travel_charged": 1 if int(row.get("custom_travel_charged") or 0) else 0,
            "travel_miles_one_way": float(row.get("custom_travel_miles_one_way") or 0),
            "return_trip_required": int(row.get("custom_return_trip_required") or 0),
            "total_travel_miles": float(row.get("custom_total_travel_miles") or 0),
            "worker": worker_context.get("worker_label") or "",
            "location": row.get("location") or "",
            "notes": row.get("description") or "",
            "record_url": f"/session_worker_db/calendar_details?event={row.get('name')}",
            "session_number": int(row.get("custom_session_number") or 0),
            "total_sessions": int(row.get("custom_total_sessions") or 0),
            "progress_text": row.get("custom_progress_text") or "",
            "booking_warning": row.get("custom_booking_warning") or "",
        })

    return events


def _get_client_display_name(client_name):
    client_doc = frappe.get_doc("Client", client_name)
    full_name = (client_doc.get("full_name") or "").strip()
    if full_name:
        return full_name

    first_name = client_doc.get("first_name")
    last_name = client_doc.get("last_name")
    display_name = " ".join([part for part in [first_name, last_name] if part]).strip()
    return display_name or client_doc.name


def _build_client_label(client_row):
    full_name = (client_row.get("full_name") or "").strip()
    if full_name:
        return full_name

    first_name = client_row.get("first_name")
    last_name = client_row.get("last_name")
    display_name = " ".join([part for part in [first_name, last_name] if part]).strip()
    return display_name or client_row.get("name")


def _format_time_range(start_dt, end_dt):
    if not start_dt:
        return ""
    start_text = start_dt.strftime("%H:%M")
    end_text = end_dt.strftime("%H:%M") if end_dt else ""
    return f"{start_text} - {end_text}" if end_text else start_text
