import frappe
from frappe import _
from frappe.utils import add_to_date, getdate, get_datetime, get_fullname
from dashboard.api.shared.session_worker_view_mode import get_session_worker_view_mode
from dashboard.api.shared.coach_view_mode import get_coach_view_mode


DASHBOARD_ADMIN_USERS = [
    "hq@theresilientkid.co.uk",
    "office@theresilientpeople.uk",
]

SESSION_WORKER_DASHBOARD = "session_worker"
COACH_DASHBOARD = "coach"
FRANCHISOR_DASHBOARD = "franchisor"

COACH_ME_VALUE = "__coach_me__"
FRANCHISOR_ME_VALUE = "__franchisor_me__"
COACH_PREFIX = "__coach__:"
WORKER_PREFIX = "__worker__:"

FREE_TRAVEL_MILES_ONE_WAY = 10
TRAVEL_EXCLUDED_SESSION_TYPES = ["Parent Check-In"]


def _require_logged_in_user():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)
    return frappe.session.user


def _is_dashboard_admin():
    return (frappe.session.user or "").strip().lower() in {email.lower() for email in DASHBOARD_ADMIN_USERS}


def _normalise_dashboard_type(dashboard_type=None):
    value = (dashboard_type or "").strip().lower()

    if value in [SESSION_WORKER_DASHBOARD, COACH_DASHBOARD, FRANCHISOR_DASHBOARD]:
        return value

    try:
        referrer = ""
        if getattr(frappe, "request", None):
            referrer = frappe.request.headers.get("Referer") or ""

        if "/coach_db/" in referrer:
            return COACH_DASHBOARD
        if "/franchisor_db/" in referrer:
            return FRANCHISOR_DASHBOARD
        if "/session_worker_db/" in referrer:
            return SESSION_WORKER_DASHBOARD
    except Exception:
        pass

    return SESSION_WORKER_DASHBOARD


def _get_record_base_url(dashboard_type):
    if dashboard_type == COACH_DASHBOARD:
        return "/coach_db/calendar_details"
    if dashboard_type == FRANCHISOR_DASHBOARD:
        return "/franchisor_db/calendar_details"
    return "/session_worker_db/calendar_details"


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
        "first_name",
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


def _get_client_display_from_row(row):
    if not row:
        return ""

    for fieldname in ["full_name", "preferred_name"]:
        value = (row.get(fieldname) or "").strip()
        if value:
            return value

    first = (row.get("name1") or row.get("first_name") or "").strip()
    last = (row.get("last_name") or "").strip()
    display_name = " ".join([part for part in [first, last] if part]).strip()

    return display_name or row.get("name") or ""


def _get_client_display_name(client_name):
    row = _get_client_row(client_name)
    return _get_client_display_from_row(row) if row else client_name


def _get_client_rows_all(limit=5000):
    if not frappe.db.exists("DocType", "Client"):
        return []

    return frappe.get_all(
        "Client",
        fields=_get_client_base_fields(),
        order_by="full_name asc",
        limit_page_length=limit,
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
    rows_by_name = {}

    if meta.has_field("primary_coach"):
        for row in frappe.get_all(
            "Client",
            fields=_get_client_base_fields(),
            filters={"primary_coach": coach},
            order_by="full_name asc",
            limit_page_length=3000,
            ignore_permissions=True,
        ):
            rows_by_name[row.name] = row

    if meta.has_field("attending_coach"):
        for row in frappe.get_all(
            "Client",
            fields=_get_client_base_fields(),
            filters={"attending_coach": coach},
            order_by="full_name asc",
            limit_page_length=3000,
            ignore_permissions=True,
        ):
            rows_by_name[row.name] = row

    return sorted(
        rows_by_name.values(),
        key=lambda row: (_get_client_display_from_row(row) or row.get("name") or "").lower(),
    )


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


def _get_coach_label(coach):
    if not coach:
        return ""

    if not frappe.db.exists("DocType", "Coach"):
        return coach

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
                    "label": _get_label(row, ["sw_name", "session_worker_name", "full_name", "employee_name", "user_full_name", "title", "name"]),
                }

    for label_field in label_fields:
        if fullname and meta.has_field(label_field):
            row = frappe.db.get_value(doctype, {label_field: fullname}, fields, as_dict=True)
            if row:
                return {
                    "doctype": doctype,
                    "name": row.get("name"),
                    "label": _get_label(row, ["sw_name", "session_worker_name", "full_name", "employee_name", "user_full_name", "title", "name"]),
                }

    return None


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


def _coach_can_view_client(client_row, coach_context):
    if coach_context.get("is_dashboard_admin"):
        return True

    coach_name = (coach_context.get("coach_name") or "").strip()
    if not coach_name:
        return False

    return client_row.get("primary_coach") == coach_name or client_row.get("attending_coach") == coach_name


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


def _get_session_worker_client_options(worker_context):
    if not frappe.db.exists("DocType", "Client"):
        return []

    client_meta = frappe.get_meta("Client")
    if not client_meta.has_field("session_worker"):
        return []

    filters = {}
    if not worker_context.get("is_dashboard_admin"):
        worker_name = (worker_context.get("worker_name") or "").strip()
        if not worker_name:
            return []
        filters["session_worker"] = worker_name

    rows = frappe.get_all(
        "Client",
        fields=_get_client_base_fields(),
        filters=filters,
        order_by="full_name asc",
        limit_page_length=1000,
        ignore_permissions=True,
    )

    return [{"value": row.get("name"), "label": _get_client_display_from_row(row)} for row in rows]


def _get_coach_calendar_for_options(coach_context):
    options = [
        {
            "value": COACH_ME_VALUE,
            "label": coach_context.get("coach_label") or "My Calendar",
        }
    ]

    if not frappe.db.exists("DocType", "Client"):
        return options

    coach_name = coach_context.get("coach_name")
    rows_by_name = {}

    if coach_context.get("is_dashboard_admin"):
        for row in frappe.get_all(
            "Client",
            fields=["name", "session_worker"],
            limit_page_length=1000,
            ignore_permissions=True,
        ):
            rows_by_name[row.name] = row
    else:
        if not coach_name:
            return options

        client_meta = frappe.get_meta("Client")

        if client_meta.has_field("primary_coach"):
            for row in frappe.get_all(
                "Client",
                fields=["name", "session_worker"],
                filters={"primary_coach": coach_name},
                limit_page_length=1000,
                ignore_permissions=True,
            ):
                rows_by_name[row.name] = row

        if client_meta.has_field("attending_coach"):
            for row in frappe.get_all(
                "Client",
                fields=["name", "session_worker"],
                filters={"attending_coach": coach_name},
                limit_page_length=1000,
                ignore_permissions=True,
            ):
                rows_by_name[row.name] = row

    worker_names = sorted({
        row.get("session_worker")
        for row in rows_by_name.values()
        if row.get("session_worker")
    })

    for worker in worker_names:
        options.append({
            "value": worker,
            "label": _get_session_worker_label(worker),
        })

    return options


def _get_franchisor_calendar_for_options():
    options = [{"value": FRANCHISOR_ME_VALUE, "label": "Me"}]

    if frappe.db.exists("DocType", "Coach"):
        meta = frappe.get_meta("Coach")
        fields = ["name"]

        for fieldname in ["coach_name", "full_name", "employee_name", "user_full_name", "title"]:
            if meta.has_field(fieldname):
                fields.append(fieldname)

        for coach in frappe.get_all(
            "Coach",
            fields=fields,
            order_by="name asc",
            limit_page_length=1000,
            ignore_permissions=True,
        ):
            options.append({
                "value": COACH_PREFIX + coach.get("name"),
                "label": "Coach: " + _get_label(coach, ["coach_name", "full_name", "employee_name", "user_full_name", "title", "name"]),
            })

    if frappe.db.exists("DocType", "Session Worker"):
        meta = frappe.get_meta("Session Worker")
        fields = ["name"]

        for fieldname in ["sw_name", "session_worker_name", "full_name", "employee_name", "user_full_name", "title"]:
            if meta.has_field(fieldname):
                fields.append(fieldname)

        for worker in frappe.get_all(
            "Session Worker",
            fields=fields,
            order_by="name asc",
            limit_page_length=1000,
            ignore_permissions=True,
        ):
            options.append({
                "value": WORKER_PREFIX + worker.get("name"),
                "label": "Session Worker: " + _get_label(worker, ["sw_name", "session_worker_name", "full_name", "employee_name", "user_full_name", "title", "name"]),
            })

    return options


def _get_selected_calendar_for(dashboard_type, selected_calendar_for, context=None):
    selected_calendar_for = (selected_calendar_for or "").strip()

    if dashboard_type == COACH_DASHBOARD:
        options = _get_coach_calendar_for_options(context)
        allowed = {row["value"] for row in options}
        return (selected_calendar_for if selected_calendar_for in allowed else COACH_ME_VALUE), options

    if dashboard_type == FRANCHISOR_DASHBOARD:
        options = _get_franchisor_calendar_for_options()
        allowed = {row["value"] for row in options}
        return (selected_calendar_for if selected_calendar_for in allowed else FRANCHISOR_ME_VALUE), options

    return "", []


def _get_franchisor_current_calendar_label(selected_calendar_for):
    if selected_calendar_for == FRANCHISOR_ME_VALUE:
        return "Me"

    if selected_calendar_for.startswith(COACH_PREFIX):
        coach = selected_calendar_for.replace(COACH_PREFIX, "", 1)
        return "Coach: " + _get_coach_label(coach)

    if selected_calendar_for.startswith(WORKER_PREFIX):
        worker = selected_calendar_for.replace(WORKER_PREFIX, "", 1)
        return "Session Worker: " + _get_session_worker_label(worker)

    return "Calendar"


def _get_client_rows_for_coach_calendar(selected_calendar_for, coach_context):
    if selected_calendar_for == COACH_ME_VALUE:
        if coach_context.get("is_dashboard_admin"):
            return _get_client_rows_all(limit=1000)

        return _get_client_rows_for_coach(coach_context.get("coach_name"))

    return _get_client_rows_for_worker(selected_calendar_for)


def _get_client_rows_for_franchisor_calendar(selected_calendar_for):
    if selected_calendar_for == FRANCHISOR_ME_VALUE:
        return _get_client_rows_all()

    if selected_calendar_for.startswith(COACH_PREFIX):
        return _get_client_rows_for_coach(selected_calendar_for.replace(COACH_PREFIX, "", 1))

    if selected_calendar_for.startswith(WORKER_PREFIX):
        return _get_client_rows_for_worker(selected_calendar_for.replace(WORKER_PREFIX, "", 1))

    return []


def _get_client_options_for_calendar(dashboard_type, selected_calendar_for, context=None):
    if dashboard_type == COACH_DASHBOARD:
        rows = _get_client_rows_for_coach_calendar(selected_calendar_for, context)
        options = []

        for row in rows:
            if not _coach_can_view_client(row, context):
                continue

            options.append({
                "value": row.get("name"),
                "label": _get_client_display_from_row(row),
            })

        return options

    if dashboard_type == FRANCHISOR_DASHBOARD:
        rows = _get_client_rows_for_franchisor_calendar(selected_calendar_for)
        return [
            {
                "value": row.get("name"),
                "label": _get_client_display_from_row(row),
            }
            for row in rows
            if row.get("name")
        ]

    return _get_session_worker_client_options(context)


def _event_has_field(fieldname):
    if frappe.db.exists("DocField", {"parent": "Event", "fieldname": fieldname}):
        return True

    if frappe.db.exists("Custom Field", {"dt": "Event", "fieldname": fieldname}):
        return True

    return False


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

    if _event_has_field("custom_session_type"):
        fields.append("custom_session_type")

    if _event_has_field("appointment_status"):
        fields.append("appointment_status")

    return fields


def _set_session_type(doc, value):
    if _event_has_field("custom_session_type"):
        doc.custom_session_type = value
        return

    if _event_has_field("custom_appointment_type"):
        doc.custom_appointment_type = _find_appointment_template_name(value) or ""


def _find_appointment_template_name(label):
    if not label or not frappe.db.exists("DocType", "Appointment Template"):
        return ""

    if frappe.db.exists("Appointment Template", label):
        return label

    meta = frappe.get_meta("Appointment Template")
    for fieldname in ["appointment_type", "title", "template_name"]:
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
    doc = frappe.db.get_value("Event", {"name": event_name}, _get_event_fields(), as_dict=True)
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

def _get_therapy_location_text(location_name):
    if not location_name:
        return ""

    if not frappe.db.exists("Therapy Location", location_name):
        return location_name

    location_doc = frappe.get_doc("Therapy Location", location_name)

    location_type = (location_doc.get("location_type") or "").strip()

    if location_type == "Online":
        return "Google Meet"

    parts = [
        location_doc.get("address_line_1"),
        location_doc.get("address_line_2"),
        location_doc.get("city"),
        location_doc.get("postal_code"),
    ]

    address = ", ".join([p.strip() for p in parts if p and p.strip()])

    return address or location_doc.get("location_name") or location_name


def _get_client_therapy_location(client_doc):
    if not client_doc:
        return "", ""

    therapy_location = ""

    if client_doc.meta.has_field("therapy_location"):
        therapy_location = client_doc.get("therapy_location") or ""

    return therapy_location, _get_therapy_location_text(therapy_location)

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


def _format_time_range(start_dt, end_dt):
    if not start_dt:
        return ""
    start_text = start_dt.strftime("%H:%M")
    end_text = end_dt.strftime("%H:%M") if end_dt else ""
    return f"{start_text} - {end_text}" if end_text else start_text


def _get_event_rows_for_dashboard(dashboard_type, range_start_date, range_end_date, selected_calendar_for, context):
    if not _event_has_field("custom_client"):
        return [], {}

    has_worker_field = _event_has_field("custom_session_worker")

    base_filters = [
        ["Event", "starts_on", ">=", f"{range_start_date} 00:00:00"],
        ["Event", "starts_on", "<=", f"{range_end_date} 23:59:59"],
    ]

    #
    # SESSION WORKER DASHBOARD
    # Show appointments assigned to the logged-in session worker via Event.custom_session_worker.
    #
    if dashboard_type == SESSION_WORKER_DASHBOARD:
        if not has_worker_field:
            return [], {}

        if context.get("is_dashboard_admin"):
            rows = frappe.get_all(
                "Event",
                fields=_get_event_fields(),
                filters=base_filters,
                order_by="starts_on asc",
                limit_page_length=1000,
                ignore_permissions=True,
            )
        else:
            worker_name = (context.get("worker_name") or "").strip()
            if not worker_name:
                return [], {}

            filters = base_filters + [
                ["Event", "custom_session_worker", "=", worker_name],
            ]

            rows = frappe.get_all(
                "Event",
                fields=_get_event_fields(),
                filters=filters,
                order_by="starts_on asc",
                limit_page_length=1000,
                ignore_permissions=True,
            )

        client_names = sorted({
            row.get("custom_client")
            for row in rows
            if row.get("custom_client")
        })

        client_map = {
            client_name: _get_client_row(client_name)
            for client_name in client_names
        }

        return rows, client_map

    #
    # COACH DASHBOARD
    #
    if dashboard_type == COACH_DASHBOARD:
        if selected_calendar_for == COACH_ME_VALUE:
            client_rows = _get_client_rows_for_coach_calendar(selected_calendar_for, context)
            client_map = {row.get("name"): row for row in client_rows if row.get("name")}

            if not client_map:
                return [], {}

            filters = base_filters + [
                ["Event", "custom_client", "in", list(client_map.keys())],
                ["Event", "owner", "=", context.get("view_as_user") or frappe.session.user],
            ]

            rows = frappe.get_all(
                "Event",
                fields=_get_event_fields(),
                filters=filters,
                order_by="starts_on asc",
                limit_page_length=1000,
                ignore_permissions=True,
            )

            if has_worker_field:
                rows = [
                    row for row in rows
                    if not (row.get("custom_session_worker") or "").strip()
                ]

            return rows, client_map

        if not has_worker_field:
            return [], {}

        filters = base_filters + [
            ["Event", "custom_session_worker", "=", selected_calendar_for],
        ]

        rows = frappe.get_all(
            "Event",
            fields=_get_event_fields(),
            filters=filters,
            order_by="starts_on asc",
            limit_page_length=1000,
            ignore_permissions=True,
        )

        client_names = sorted({
            row.get("custom_client")
            for row in rows
            if row.get("custom_client")
        })

        client_map = {
            client_name: _get_client_row(client_name)
            for client_name in client_names
        }

        return rows, client_map

    #
    # FRANCHISOR DASHBOARD
    #
    if dashboard_type == FRANCHISOR_DASHBOARD:
        if selected_calendar_for == FRANCHISOR_ME_VALUE:
            filters = base_filters + [
                ["Event", "owner", "=", context.get("view_as_user") or frappe.session.user],
            ]

            rows = frappe.get_all(
                "Event",
                fields=_get_event_fields(),
                filters=filters,
                order_by="starts_on asc",
                limit_page_length=1000,
                ignore_permissions=True,
            )

            if has_worker_field:
                rows = [
                    row for row in rows
                    if not (row.get("custom_session_worker") or "").strip()
                ]

        elif selected_calendar_for.startswith(WORKER_PREFIX):
            if not has_worker_field:
                return [], {}

            worker = selected_calendar_for.replace(WORKER_PREFIX, "", 1)

            filters = base_filters + [
                ["Event", "custom_session_worker", "=", worker],
            ]

            rows = frappe.get_all(
                "Event",
                fields=_get_event_fields(),
                filters=filters,
                order_by="starts_on asc",
                limit_page_length=1000,
                ignore_permissions=True,
            )

        elif selected_calendar_for.startswith(COACH_PREFIX):
            coach = selected_calendar_for.replace(COACH_PREFIX, "", 1)
            client_rows = _get_client_rows_for_coach(coach)
            client_map = {row.get("name"): row for row in client_rows if row.get("name")}

            if not client_map:
                return [], {}

            filters = base_filters + [
                ["Event", "custom_client", "in", list(client_map.keys())],
            ]

            rows = frappe.get_all(
                "Event",
                fields=_get_event_fields(),
                filters=filters,
                order_by="starts_on asc",
                limit_page_length=1000,
                ignore_permissions=True,
            )

            if has_worker_field:
                rows = [
                    row for row in rows
                    if not (row.get("custom_session_worker") or "").strip()
                ]

            return rows, client_map

        else:
            return [], {}

        client_names = sorted({
            row.get("custom_client")
            for row in rows
            if row.get("custom_client")
        })

        client_map = {
            client_name: _get_client_row(client_name)
            for client_name in client_names
        }

        return rows, client_map

    return [], {}


def _build_event_response(row, dashboard_type, selected_calendar_for, context, client_map):
    raw_status = _get_event_status(row)
    ui_status = _map_event_status_to_ui(raw_status)

    if ui_status == "Cancelled":
        return None

    start_dt = get_datetime(row.get("starts_on"))
    end_dt = get_datetime(row.get("ends_on")) if row.get("ends_on") else None
    custom_client = row.get("custom_client")
    client_row = client_map.get(custom_client) if client_map else None

    is_private_for_viewing_coach = False

    if dashboard_type == COACH_DASHBOARD and not _coach_can_view_client(client_row or {}, context):
        is_private_for_viewing_coach = True

    if (
        dashboard_type == SESSION_WORKER_DASHBOARD
        and int(context.get("is_view_mode") or 0)
        and (context.get("view_scope") or "").lower() == "coach"
        and not context.get("is_dashboard_admin")
    ):
        coach_name = (context.get("viewer_coach_name") or "").strip()

        if not coach_name:
            is_private_for_viewing_coach = True
        else:
            is_private_for_viewing_coach = not (
                (client_row or {}).get("primary_coach") == coach_name
                or (client_row or {}).get("attending_coach") == coach_name
            )

    if is_private_for_viewing_coach:
        return {
            "id": row.get("name"),
            "name": row.get("name"),
            "title": "Private",
            "client_name": "",
            "date": start_dt.strftime("%Y-%m-%d"),
            "start_time": start_dt.strftime("%H:%M"),
            "end_time": end_dt.strftime("%H:%M") if end_dt else start_dt.strftime("%H:%M"),
            "status": raw_status,
            "ui_status": ui_status,
            "type": "",
            "billing_type": "",
            "travel_charged": 0,
            "travel_miles_one_way": 0,
            "return_trip_required": 0,
            "total_travel_miles": 0,
            "worker": context.get("worker_label") or "Session Worker",
            "location": "",
            "notes": "",
            "record_url": "",
            "session_number": 0,
            "total_sessions": 0,
            "progress_text": "",
            "booking_warning": "",
            "is_private": 1,
        }

    session_type = _get_effective_session_type(row)
    title = row.get("subject") or "Session"

    if custom_client:
        try:
            title = _get_client_display_name(custom_client) + " - " + session_type
        except Exception:
            pass

    worker_label = ""

    if dashboard_type == COACH_DASHBOARD:
        worker_label = "Me" if selected_calendar_for == COACH_ME_VALUE else _get_session_worker_label(selected_calendar_for)
    elif dashboard_type == FRANCHISOR_DASHBOARD:
        worker_label = _get_franchisor_current_calendar_label(selected_calendar_for)
        if client_row and client_row.get("session_worker"):
            worker_label = _get_session_worker_label(client_row.get("session_worker"))
    else:
        worker_label = context.get("worker_label") or ""

    record_url = f"{_get_record_base_url(dashboard_type)}?event={row.get('name')}"

    return {
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
        "worker": worker_label,
        "location": row.get("location") or "",
        "notes": row.get("description") or "",
        "record_url": record_url,
        "session_number": int(row.get("custom_session_number") or 0),
        "total_sessions": int(row.get("custom_total_sessions") or 0),
        "progress_text": row.get("custom_progress_text") or "",
        "booking_warning": row.get("custom_booking_warning") or "",
        "is_private": 0,
    }


def _get_events(range_start_date, range_end_date, dashboard_type, selected_calendar_for, context):
    rows, client_map = _get_event_rows_for_dashboard(
        dashboard_type,
        range_start_date,
        range_end_date,
        selected_calendar_for,
        context,
    )

    events = []
    for row in rows:
        item = _build_event_response(row, dashboard_type, selected_calendar_for, context, client_map)
        if item:
            events.append(item)

    return events


def _get_context_for_dashboard(dashboard_type):
    if dashboard_type == COACH_DASHBOARD:
        return _get_current_coach_context(frappe.session.user)

    if dashboard_type == FRANCHISOR_DASHBOARD:
        return {
            "user": frappe.session.user,
            "resolution_note": "",
            "is_dashboard_admin": True,
        }

    return _get_current_session_worker_context(frappe.session.user)


def _get_context_for_calendar_request(dashboard_type, view_as=None, viewer=None):
    view_as = (view_as or "").strip()
    viewer = (viewer or "").strip().lower()

    if dashboard_type == COACH_DASHBOARD and view_as:
        view_mode = get_coach_view_mode(
            scope=viewer,
            coach_name=view_as,
        )

        if not view_mode.get("is_view_mode"):
            frappe.throw(_("You do not have permission to view this coach."), frappe.PermissionError)

        coach_name = view_mode.get("view_coach_name")
        coach_user = (
            frappe.db.get_value("Coach", coach_name, "user")
            or frappe.db.get_value("Coach", coach_name, "coach_email")
            or ""
        )

        return {
            "user": frappe.session.user,
            "coach_name": coach_name,
            "coach_label": view_mode.get("view_coach_display_name"),
            "resolution_note": "Read-only coach calendar view.",
            "is_dashboard_admin": False,
            "is_view_mode": 1,
            "view_scope": viewer,
            "view_as_user": coach_user,
        }

    if dashboard_type != SESSION_WORKER_DASHBOARD:
        return _get_context_for_dashboard(dashboard_type)

    if not view_as:
        return _get_context_for_dashboard(dashboard_type)

    view_mode = get_session_worker_view_mode(
        scope=viewer,
        worker_name=view_as,
    )

    if not view_mode.get("is_view_mode"):
        frappe.throw(_("You do not have permission to view this session worker."), frappe.PermissionError)

    coach_context = _get_current_coach_context(frappe.session.user)

    return {
        "user": frappe.session.user,
        "worker_doctype": "Session Worker",
        "worker_name": view_mode.get("view_worker_name"),
        "worker_label": view_mode.get("view_worker_display_name"),
        "resolution_note": "Read-only session worker calendar view.",
        "is_dashboard_admin": True if viewer in ["franchisor", "admin"] or _is_dashboard_admin() else False,
        "is_view_mode": 1,
        "view_scope": viewer,
        "viewer_coach_name": coach_context.get("coach_name") or "",
        "viewer_coach_label": coach_context.get("coach_label") or "",
    }
    

def _get_current_worker_name_and_label(dashboard_type, selected_calendar_for, context):
    if dashboard_type == COACH_DASHBOARD:
        return (
            selected_calendar_for,
            "Me" if selected_calendar_for == COACH_ME_VALUE else _get_session_worker_label(selected_calendar_for),
        )

    if dashboard_type == FRANCHISOR_DASHBOARD:
        return selected_calendar_for, _get_franchisor_current_calendar_label(selected_calendar_for)

    return context.get("worker_name") or "", context.get("worker_label") or ""


@frappe.whitelist(allow_guest=False)
def get_calendar_bootstrap(
    week_start=None,
    view=None,
    date=None,
    selected_worker=None,
    selected_calendar_for=None,
    calendar_for=None,
    dashboard_type=None,
    view_as=None,
    viewer=None,
):
    
    _require_logged_in_user()

    dashboard_type = _normalise_dashboard_type(dashboard_type)
    context = _get_context_for_calendar_request(
        dashboard_type=dashboard_type,
        view_as=view_as,
        viewer=viewer,
    )

    selected_calendar_for = selected_calendar_for or calendar_for or selected_worker

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

    if dashboard_type in [COACH_DASHBOARD, FRANCHISOR_DASHBOARD]:
        selected_calendar_for, calendar_for_options = _get_selected_calendar_for(
            dashboard_type,
            selected_calendar_for,
            context,
        )
    else:
        selected_calendar_for = ""
        calendar_for_options = []

    current_worker_name, current_worker_label = _get_current_worker_name_and_label(
        dashboard_type,
        selected_calendar_for,
        context,
    )

    return {
        "events": _get_events(range_start_date, range_end_date, dashboard_type, selected_calendar_for, context),
        "clients": _get_client_options_for_calendar(dashboard_type, selected_calendar_for, context),
        "session_workers": calendar_for_options,
        "calendar_for_options": calendar_for_options,
        "selected_worker": selected_calendar_for,
        "selected_calendar_for": selected_calendar_for,
        "current_user": frappe.session.user,
        "current_user_fullname": get_fullname(frappe.session.user),
        "current_worker_name": current_worker_name,
        "current_worker_label": current_worker_label,
        "session_worker_doctype": context.get("worker_doctype") or "Session Worker",
        "resolution_note": context.get("resolution_note") or "",
        "is_dashboard_admin": 1 if context.get("is_dashboard_admin") else 0,
        "dashboard_type": dashboard_type,
    }


@frappe.whitelist(allow_guest=False)
def get_event_details(event=None, dashboard_type=None, view_as=None, viewer=None):
    _require_logged_in_user()

    dashboard_type = _normalise_dashboard_type(dashboard_type)
    context = _get_context_for_calendar_request(
        dashboard_type=dashboard_type,
        view_as=view_as,
        viewer=viewer,
    )

    event_name = _coalesce_str("event", event)
    if not event_name:
        frappe.throw(_("Event is required."))

    event_doc = _get_event_doc(event_name)
    client = (event_doc.get("custom_client") or "").strip()
    client_row = _get_client_row(client)

    if dashboard_type == SESSION_WORKER_DASHBOARD:
        if client and not _client_belongs_to_session_worker(client, context):
            frappe.throw(_("You do not have permission to view this session."), frappe.PermissionError)

    if dashboard_type == COACH_DASHBOARD:
        if not client_row or not _coach_can_view_client(client_row, context):
            frappe.throw(_("This appointment belongs to another coach. Details are hidden."), frappe.PermissionError)

    start_dt = get_datetime(event_doc.get("starts_on")) if event_doc.get("starts_on") else None
    end_dt = get_datetime(event_doc.get("ends_on")) if event_doc.get("ends_on") else None

    raw_status = _get_event_status(event_doc)
    ui_status = _map_event_status_to_ui(raw_status)
    session_type = _get_effective_session_type(event_doc)

    worker_label = ""

    if dashboard_type == COACH_DASHBOARD:
        worker_label = _get_session_worker_label(client_row.get("session_worker")) if client_row and client_row.get("session_worker") else "Me"
    elif dashboard_type == FRANCHISOR_DASHBOARD:
        worker_label = _get_session_worker_label(client_row.get("session_worker")) if client_row and client_row.get("session_worker") else "Me"
    else:
        worker_label = context.get("worker_label") or ""

    return {
        "name": event_doc.get("name"),
        "client_name": client,
        "client_label": _get_client_display_name(client) if client else event_doc.get("subject") or "Session",
        "appointment_type": session_type,
        "status": raw_status,
        "ui_status": ui_status,
        "worker_label": worker_label,
        "display_date": start_dt.strftime("%A, %d %B %Y") if start_dt else "",
        "display_time": _format_time_range(start_dt, end_dt),
        "session_date": start_dt.strftime("%Y-%m-%d") if start_dt else "",
        "start_time": start_dt.strftime("%H:%M") if start_dt else "",
        "location": event_doc.get("location") or "",
        "billing_type": _get_effective_billing_type(event_doc),
        "travel_charged": 1 if int(event_doc.get("custom_travel_charged") or 0) else 0,
        "travel_miles_one_way": float(event_doc.get("custom_travel_miles_one_way") or 0),
        "total_travel_miles": float(event_doc.get("custom_total_travel_miles") or 0),
        "client_notes": _get_client_notes(client) if client else [],
        "session_number": int(event_doc.get("custom_session_number") or 0),
        "total_sessions": int(event_doc.get("custom_total_sessions") or 0),
        "progress_text": event_doc.get("custom_progress_text") or "",
        "booking_warning": event_doc.get("custom_booking_warning") or "",
    }


def _can_book_or_edit_client(client, dashboard_type, context):
    client_row = _get_client_row(client)

    if not client_row:
        frappe.throw(_("Selected client was not found."))

    if dashboard_type == SESSION_WORKER_DASHBOARD:
        if not _client_belongs_to_session_worker(client, context):
            frappe.throw(_("This client is not assigned to the logged-in session worker."), frappe.PermissionError)

    if dashboard_type == COACH_DASHBOARD:
        if not _coach_can_view_client(client_row, context):
            frappe.throw(_("You do not have permission to book this client."), frappe.PermissionError)

    return client_row


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
    dashboard_type=None,
):
    _require_logged_in_user()

    dashboard_type = _normalise_dashboard_type(dashboard_type)
    context = _get_context_for_dashboard(dashboard_type)

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

    client_row = _can_book_or_edit_client(client, dashboard_type, context)

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

    client_doc = frappe.get_doc("Client", client)
    client_travel = _get_client_travel_defaults(client_doc)
    final_travel_charged = _to_int(travel_charged, default=int(client_travel.get("travel_charged") or 0))

    if _event_has_field("custom_travel_charged"):
        event.custom_travel_charged = 1 if final_travel_charged else 0

    if _event_has_field("custom_travel_miles_one_way"):
        event.custom_travel_miles_one_way = float(client_travel.get("miles_one_way") or 0)

    if _event_has_field("custom_return_trip_required"):
        event.custom_return_trip_required = 1

    if _event_has_field("custom_session_worker") and client_row.get("session_worker"):
        event.custom_session_worker = client_row.get("session_worker")

    if _event_has_field("custom_total_travel_miles"):
        event.custom_total_travel_miles = _get_effective_total_travel_miles(event)

    if _event_has_field("custom_appointment_status"):
        event.custom_appointment_status = "Scheduled"
    elif _event_has_field("appointment_status"):
        event.appointment_status = "Open"

    if _event_has_field("status"):
        event.status = "Open"

    if _event_has_field("custom_therapy_location"):
        event.custom_therapy_location = therapy_location
    
    if _event_has_field("location"):
        event.location = location

    if notes:
        event.description = notes

    event.insert(ignore_permissions=True)

    return {
        "name": event.name,
        "title": event.subject,
        "record_url": f"{_get_record_base_url(dashboard_type)}?event={event.name}",
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
    dashboard_type=None,
):
    _require_logged_in_user()

    dashboard_type = _normalise_dashboard_type(dashboard_type)
    context = _get_context_for_dashboard(dashboard_type)

    event_name = _coalesce_str("event", event)
    if not event_name:
        frappe.throw(_("Event is required."))

    event_doc = frappe.get_doc("Event", event_name)
    client = (event_doc.get("custom_client") or "").strip()
    client_row = _get_client_row(client)

    if dashboard_type == SESSION_WORKER_DASHBOARD:
        if client and not _client_belongs_to_session_worker(client, context):
            frappe.throw(_("You do not have permission to update this session."), frappe.PermissionError)

    if dashboard_type == COACH_DASHBOARD:
        if not client_row or not _coach_can_view_client(client_row, context):
            frappe.throw(_("You cannot edit this appointment because it belongs to another coach."), frappe.PermissionError)

    booking_date = _coalesce_str("booking_date", booking_date)
    booking_time = _coalesce_str("booking_time", booking_time)
    status = _coalesce_str("status", status)
    appointment_type = _coalesce_str("appointment_type", appointment_type)
    location = _coalesce_str("location", location)
    billing_type = _coalesce_str("billing_type", billing_type)
    travel_charged = _coalesce_raw("travel_charged", travel_charged)

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
    
    if _event_has_field("custom_therapy_location") and client:
        client_doc = frappe.get_doc("Client", client)
    
        if client_doc.meta.has_field("therapy_location"):
            event_doc.custom_therapy_location = client_doc.get("therapy_location") or ""

    if _event_has_field("event_type"):
        event_doc.event_type = "Public"

    if _event_has_field("custom_travel_charged"):
        event_doc.custom_travel_charged = 1 if _to_int(travel_charged) else 0

    if client and frappe.db.exists("Client", client):
        client_doc = frappe.get_doc("Client", client)
        client_travel = _get_client_travel_defaults(client_doc)

        if _event_has_field("custom_travel_miles_one_way"):
            event_doc.custom_travel_miles_one_way = float(client_travel.get("miles_one_way") or 0)

        if _event_has_field("custom_return_trip_required"):
            event_doc.custom_return_trip_required = 1

        if _event_has_field("custom_session_worker") and client_row and client_row.get("session_worker"):
            event_doc.custom_session_worker = client_row.get("session_worker")

    if _event_has_field("custom_total_travel_miles"):
        event_doc.custom_total_travel_miles = _get_effective_total_travel_miles(event_doc)

    if client:
        client_label = _get_client_display_name(client)
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
def add_client_note(client=None, session_date=None, session_type=None, notes=None, dashboard_type=None):
    _require_logged_in_user()

    dashboard_type = _normalise_dashboard_type(dashboard_type)
    context = _get_context_for_dashboard(dashboard_type)

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

    if dashboard_type == SESSION_WORKER_DASHBOARD:
        if not _client_belongs_to_session_worker(client, context):
            frappe.throw(_("You do not have permission to add notes for this client."), frappe.PermissionError)

    if dashboard_type == COACH_DASHBOARD:
        client_row = _get_client_row(client)
        if not client_row or not _coach_can_view_client(client_row, context):
            frappe.throw(_("You cannot add notes for this client."), frappe.PermissionError)

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
