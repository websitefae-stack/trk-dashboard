import frappe
from frappe import _
from frappe.utils import add_to_date, getdate, get_datetime, get_fullname, now_datetime
from dashboard.api.shared.session_worker_view_mode import get_session_worker_view_mode
from dashboard.api.shared.coach_view_mode import get_coach_view_mode
from dashboard.api.shared.utils import get_label as _get_label, get_request_payload as _get_request_payload, coalesce_raw as _coalesce_raw, coalesce_str as _coalesce_str, find_session_worker_for_user as _find_session_worker_for_user
from dashboard.api.shared.clients import build_display_name as _build_client_display_name


DASHBOARD_ADMIN_USERS = [
    "hq@theresilientkid.co.uk",
    "office@theresilienthub.co.uk",
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
CLIENT_SESSION_TYPES = ["Therapy Session", "Parent Check-In"]
NON_CLIENT_TYPES = ["Initial Consultation", "Internal Training", "School Visit", "Company Meeting", "Event / Stall", "Holiday", "Personal"]


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
        "main_therapy_location",
        "client_type",
        "address",
        "city",
        "zip_code",
    ]:
        if meta.has_field(fieldname) and fieldname not in fields:
            fields.append(fieldname)

    return fields


def _get_client_row(client):
    if not client or not frappe.db.exists("Client", client):
        return None

    return frappe.db.get_value("Client", client, _get_client_base_fields(), as_dict=True)


def _get_client_display_from_row(row):
    """
    "Preferred Last (First)" when a preferred name differs from the first
    name, otherwise the plain full name - same rule the franchisor client
    list already uses (clients.build_display_name), reused here instead of
    a second, different implementation that never combined preferred name
    with the surname/brackets at all.
    """
    if not row:
        return ""

    return _build_client_display_name(row) or row.get("name") or ""

def _get_client_therapy_location_label(row):
    if not row:
        return ""

    therapy_location = (row.get("main_therapy_location") or "").strip()

    if not therapy_location:
        return ""

    return _get_therapy_location_text(therapy_location)

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

    return [
        {
            "value": row.get("name"),
            "label": _get_client_display_from_row(row),
            "therapy_location": row.get("main_therapy_location") or "",
            "therapy_location_label": _get_client_therapy_location_label(row),
        }
        for row in rows
    ]


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


def _get_client_contacts(client_name):
    if not client_name or not frappe.db.exists("Client", client_name):
        return []

    contacts = []

    try:
        client_doc = frappe.get_doc("Client", client_name)
    except Exception:
        return []

    for field in client_doc.meta.fields:
        if field.fieldtype != "Table":
            continue

        rows = client_doc.get(field.fieldname) or []

        for row in rows:
            contact_name = (
                row.get("contact")
                or row.get("contact_name")
                or row.get("name")
                or ""
            )

            label_parts = [
                row.get("contact_name"),
                row.get("full_name"),
                row.get("relationship_type"),
                row.get("email_id"),
                row.get("phone"),
            ]

            label = " - ".join([str(part).strip() for part in label_parts if part and str(part).strip()])

            if contact_name or label:
                contacts.append({
                    "value": contact_name or label,
                    "label": label or contact_name,
                })

    return contacts


def _format_school_location(row):
    parts = [
        row.get("address"),
        row.get("city"),
        row.get("zip_code"),
    ]
    return ", ".join([str(part).strip() for part in parts if part and str(part).strip()])


def _get_school_options():
    if not frappe.db.exists("DocType", "Client"):
        return []

    rows = frappe.get_all(
        "Client",
        fields=_get_client_base_fields(),
        filters={"client_type": "School"},
        order_by="full_name asc",
        limit_page_length=1000,
        ignore_permissions=True,
    )

    return [
        {
            "value": row.get("name"),
            "label": _get_client_display_from_row(row),
            "location": _format_school_location(row),
        }
        for row in rows
        if row.get("name")
    ]


def _build_client_option(row):
    return {
        "value": row.get("name"),
        "label": _get_client_display_from_row(row),
        "therapy_location": row.get("main_therapy_location") or "",
        "therapy_location_label": _get_client_therapy_location_label(row),
        "contacts": _get_client_contacts(row.get("name")),
    }


def _get_client_options_for_calendar(dashboard_type, selected_calendar_for, context=None):
    if dashboard_type == COACH_DASHBOARD:
        rows = _get_client_rows_for_coach_calendar(selected_calendar_for, context)
        options = []

        for row in rows:
            if not _coach_can_view_client(row, context):
                continue

            options.append(_build_client_option(row))

        return options

    if dashboard_type == FRANCHISOR_DASHBOARD:
        rows = _get_client_rows_for_franchisor_calendar(selected_calendar_for)

        return [
            _build_client_option(row)
            for row in rows
            if row.get("name")
        ]

    rows = _get_session_worker_client_options(context)

    for row in rows:
        row["contacts"] = _get_client_contacts(row.get("value"))

    return rows


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
        "google_meet_link",
    ]

    if _event_has_field("custom_session_type"):
        fields.append("custom_session_type")

    if _event_has_field("appointment_status"):
        fields.append("appointment_status")

    if _event_has_field("google_calendar_event_id"):
        fields.append("google_calendar_event_id")

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
    location_label = location_doc.get("location_name") or location_name

    if address:
        return location_label + " - " + address

    return location_label


def _get_client_therapy_location(client_doc):
    if not client_doc:
        return "", ""

    therapy_location = ""

    if client_doc.meta.has_field("main_therapy_location"):
        therapy_location = client_doc.get("main_therapy_location") or ""

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

def _find_calendar_conflict(event_start, event_end, dashboard_type, context):
    filters = [
        ["Event", "starts_on", "<", event_end],
        ["Event", "ends_on", ">", event_start],
    ]

    if dashboard_type == SESSION_WORKER_DASHBOARD and _event_has_field("custom_session_worker"):
        worker_name = (context.get("worker_name") or "").strip()
        if worker_name:
            filters.append(["Event", "custom_session_worker", "=", worker_name])
    else:
        filters.append(["Event", "owner", "=", context.get("view_as_user") or frappe.session.user])

    existing = frappe.get_all(
        "Event",
        fields=["name", "subject", "starts_on", "ends_on"],
        filters=filters,
        order_by="starts_on asc",
        limit_page_length=1,
        ignore_permissions=True,
    )

    return existing[0] if existing else None
    
def _create_or_update_initial_consultation_lead(lead_name, phone=None, notes=None):
    if not frappe.db.exists("DocType", "Lead"):
        return ""

    existing = None

    if phone:
        for fieldname in ["mobile_no", "phone", "phone_no"]:
            if frappe.get_meta("Lead").has_field(fieldname):
                existing = frappe.db.get_value("Lead", {fieldname: phone}, "name")
                if existing:
                    break

    if existing:
        return existing

    lead = frappe.new_doc("Lead")

    if lead.meta.has_field("lead_name"):
        lead.lead_name = lead_name
    elif lead.meta.has_field("first_name"):
        lead.first_name = lead_name

    if phone:
        for fieldname in ["mobile_no", "phone", "phone_no"]:
            if lead.meta.has_field(fieldname):
                lead.set(fieldname, phone)
                break

    if notes and lead.meta.has_field("notes"):
        # "notes" is a Table field (child doctype "CRM Notes": note/added_by/
        # added_on) - assigning a plain string here (lead.notes = notes) made
        # Frappe iterate over the string character-by-character trying to
        # treat each character as a child row, and crash setting internal
        # metadata on a bare str: "'str' object has no attribute 'modified'
        # and no __dict__ for setting new attributes". This is exactly the
        # crash reported when saving an Initial Consultation with notes filled in.
        lead.append("notes", {
            "doctype": "CRM Notes",
            "note": notes,
            "added_by": frappe.session.user,
            "added_on": now_datetime(),
        })

    lead.insert(ignore_permissions=True)
    return lead.name

def _get_notes_parentfield(doctype):
    """Find the Table field (options="Notes") on the given parent doctype, if any."""
    if not frappe.db.exists("DocType", doctype):
        return None

    meta = frappe.get_meta(doctype)
    for field in meta.fields:
        if field.fieldtype == "Table" and field.options == "Notes":
            return field.fieldname
    return None


def _get_client_notes_parentfield():
    return _get_notes_parentfield("Client")


def _get_notes_for_parent(doctype, parent_name):
    """Same shape as _get_client_notes(), generalised to any doctype with a Notes table (Client or Lead)."""
    if not parent_name or not frappe.db.exists(doctype, parent_name):
        return []

    parentfield = _get_notes_parentfield(doctype)
    if not parentfield:
        return []

    parent_doc = frappe.get_doc(doctype, parent_name)
    rows = parent_doc.get(parentfield) or []

    notes = []
    for row in rows:
        note_owner = row.get("owner") or ""
        note_user_name = get_fullname(note_owner) if note_owner else ""

        notes.append({
            "name": row.name,
            "client": row.get("client") or (parent_name if doctype == "Client" else ""),
            "session_date": row.get("session_date").strftime("%Y-%m-%d") if row.get("session_date") else "",
            "session_type": row.get("session_type") or "",
            "notes": row.get("notes") or "",
            "note_user": note_owner,
            "note_user_name": note_user_name or note_owner,
            "idx": row.get("idx") or 0,
        })

    notes.sort(key=lambda d: ((d.get("session_date") or ""), d.get("idx") or 0), reverse=True)
    return notes


def _get_client_notes(client_name):
    return _get_notes_for_parent("Client", client_name)


def _get_lead_notes(lead_name):
    """
    Initial Consultation notes live on the Lead's own "notes" table field,
    a child table of "CRM Notes" (note / added_by / added_on) - a different
    shape from Client's own Notes table (session_date / session_type /
    notes / client), so this is handled separately rather than forced into
    _get_notes_for_parent's Client-shaped rows.
    """
    if not lead_name or not frappe.db.exists("Lead", lead_name):
        return []

    if not frappe.get_meta("Lead").has_field("notes"):
        return []

    lead_doc = frappe.get_doc("Lead", lead_name)
    rows = lead_doc.get("notes") or []

    notes = []
    for row in rows:
        added_by = row.get("added_by") or ""
        added_on = row.get("added_on")

        notes.append({
            "name": row.name,
            "client": "",
            "session_date": added_on.strftime("%Y-%m-%d") if added_on else "",
            "session_type": "",
            "notes": row.get("note") or "",
            "note_user": added_by,
            "note_user_name": get_fullname(added_by) if added_by else "",
            "idx": row.get("idx") or 0,
        })

    notes.sort(key=lambda d: ((d.get("session_date") or ""), d.get("idx") or 0), reverse=True)
    return notes


def _add_lead_note(lead_name, notes_text):
    lead_doc = frappe.get_doc("Lead", lead_name)
    lead_doc.append("notes", {
        "doctype": "CRM Notes",
        "note": notes_text,
        "added_by": frappe.session.user,
        "added_on": now_datetime(),
    })
    lead_doc.save(ignore_permissions=True)
    return _get_lead_notes(lead_name)


def _get_lead_for_event(event_doc):
    """
    Initial Consultation appointments don't have a Client - create_booking()
    creates a Lead instead and records it as the first line of the event's
    own description ("Lead: <name>"), rather than a proper link field. Parse
    that back out so notes taken on an Initial Consultation can attach to
    the right Lead.
    """
    if not frappe.db.exists("DocType", "Lead"):
        return None

    description = event_doc.get("description") or ""
    first_line = description.splitlines()[0].strip() if description else ""
    if not first_line.startswith("Lead: "):
        return None

    lead_name = first_line[len("Lead: "):].strip()
    if not lead_name or not frappe.db.exists("Lead", lead_name):
        return None

    return lead_name


def _format_time_range(start_dt, end_dt):
    if not start_dt:
        return ""
    start_text = start_dt.strftime("%H:%M")
    end_text = end_dt.strftime("%H:%M") if end_dt else ""
    return f"{start_text} - {end_text}" if end_text else start_text


def _get_event_rows_for_dashboard(dashboard_type, range_start_date, range_end_date, selected_calendar_for, context):
    has_client_field = _event_has_field("custom_client")
    has_worker_field = _event_has_field("custom_session_worker")

    base_filters = [
        ["Event", "starts_on", ">=", f"{range_start_date} 00:00:00"],
        ["Event", "starts_on", "<=", f"{range_end_date} 23:59:59"],
    ]

    rows = []
    client_map = {}

    #
    # SESSION WORKER DASHBOARD
    #
    if dashboard_type == SESSION_WORKER_DASHBOARD:
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
            ] if has_worker_field else base_filters + [
                ["Event", "owner", "=", context.get("user") or frappe.session.user],
            ]

            rows = frappe.get_all(
                "Event",
                fields=_get_event_fields(),
                filters=filters,
                order_by="starts_on asc",
                limit_page_length=1000,
                ignore_permissions=True,
            )

    #
    # COACH DASHBOARD
    #
    elif dashboard_type == COACH_DASHBOARD:
        if selected_calendar_for == COACH_ME_VALUE:
            client_rows = _get_client_rows_for_coach_calendar(selected_calendar_for, context)
            client_map = {row.get("name"): row for row in client_rows if row.get("name")}

            owner_user = context.get("view_as_user") or frappe.session.user

            owner_filters = base_filters + [
                ["Event", "owner", "=", owner_user],
            ]

            rows = frappe.get_all(
                "Event",
                fields=_get_event_fields(),
                filters=owner_filters,
                order_by="starts_on asc",
                limit_page_length=1000,
                ignore_permissions=True,
            )

            if client_map and has_client_field:
                client_filters = base_filters + [
                    ["Event", "custom_client", "in", list(client_map.keys())],
                ]

                client_rows_for_calendar = frappe.get_all(
                    "Event",
                    fields=_get_event_fields(),
                    filters=client_filters,
                    order_by="starts_on asc",
                    limit_page_length=1000,
                    ignore_permissions=True,
                )

                by_name = {row.get("name"): row for row in rows}
                for row in client_rows_for_calendar:
                    by_name[row.get("name")] = row

                rows = sorted(
                    by_name.values(),
                    key=lambda row: row.get("starts_on") or "",
                )

            if has_worker_field:
                rows = [
                    row for row in rows
                    if not (row.get("custom_session_worker") or "").strip()
                ]

        else:
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

    #
    # FRANCHISOR DASHBOARD
    #
    elif dashboard_type == FRANCHISOR_DASHBOARD:
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
            has_coach_field = _event_has_field("custom_coach")

            if (not client_map or not has_client_field) and not has_coach_field:
                return [], {}

            by_name = {}

            if client_map and has_client_field:
                client_filters = base_filters + [
                    ["Event", "custom_client", "in", list(client_map.keys())],
                ]
                for row in frappe.get_all(
                    "Event",
                    fields=_get_event_fields(),
                    filters=client_filters,
                    order_by="starts_on asc",
                    limit_page_length=1000,
                    ignore_permissions=True,
                ):
                    by_name[row.get("name")] = row

            # Also include the coach's own client-less events (e.g. pulled in
            # from Google Calendar, or internal/personal entries) - these have
            # no custom_client, so the filter above alone would hide them.
            if has_coach_field:
                coach_filters = base_filters + [
                    ["Event", "custom_coach", "=", coach],
                ]
                for row in frappe.get_all(
                    "Event",
                    fields=_get_event_fields(),
                    filters=coach_filters,
                    order_by="starts_on asc",
                    limit_page_length=1000,
                    ignore_permissions=True,
                ):
                    by_name[row.get("name")] = row

            rows = sorted(by_name.values(), key=lambda row: row.get("starts_on") or "")

            if has_worker_field:
                rows = [
                    row for row in rows
                    if not (row.get("custom_session_worker") or "").strip()
                ]
        else:
            return [], {}

    else:
        return [], {}

    client_names = sorted({
        row.get("custom_client")
        for row in rows
        if row.get("custom_client")
    })

    if client_names:
        client_map.update({
            client_name: _get_client_row(client_name)
            for client_name in client_names
        })

    return rows, client_map


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

    if dashboard_type == COACH_DASHBOARD and custom_client and not _coach_can_view_client(client_row or {}, context):
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
            "google_meet_link": "",
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
        "client_display_name": _get_client_display_name(custom_client) if custom_client else "",
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
        "google_meet_link": row.get("google_meet_link") or "",
        "needs_linking": bool(row.get("google_calendar_event_id") and not custom_client),
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
        "schools": _get_school_options(),
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
    lead = _get_lead_for_event(event_doc) if not client else None

    if dashboard_type == SESSION_WORKER_DASHBOARD:
        if client and not _client_belongs_to_session_worker(client, context):
            frappe.throw(_("You do not have permission to view this session."), frappe.PermissionError)

    if dashboard_type == COACH_DASHBOARD:
        if client and (not client_row or not _coach_can_view_client(client_row, context)):
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

    lead_label = ""
    if lead:
        lead_label = frappe.db.get_value("Lead", lead, "lead_name") or frappe.db.get_value("Lead", lead, "first_name") or lead

    return {
        "name": event_doc.get("name"),
        "client_name": client,
        "client_label": _get_client_display_name(client) if client else event_doc.get("subject") or "Session",
        "lead_name": lead or "",
        "lead_label": lead_label,
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
        "client_notes": _get_notes_for_parent("Client", client) if client else (
            _get_lead_notes(lead) if lead else []
        ),
        "session_number": int(event_doc.get("custom_session_number") or 0),
        "total_sessions": int(event_doc.get("custom_total_sessions") or 0),
        "progress_text": event_doc.get("custom_progress_text") or "",
        "booking_warning": event_doc.get("custom_booking_warning") or "",
        "google_meet_link": event_doc.get("google_meet_link") or "",
    }


def share_event_with_admins(doc, method=None):
    """
    doc_events hook for Event (after_insert / on_update) - runs for every
    appointment regardless of how it was created, including ones pulled in
    from Google Calendar by coach_calendar_sync.

    Events are event_type="Private" so Frappe's own native permission model
    only shows an appointment to its owner - coaches shouldn't see each
    other's sessions there. HQ/office still need to see everything in the
    raw Frappe backend, so every event is shared with the admin accounts
    instead of making it Public (which would reopen it up to every coach).

    This only enqueues a background job - it must never do real work here.
    A prior version called frappe.share.add() directly inside this hook,
    which internally requires the *currently acting* user to already have
    share permission on the event (frappe.share.check_share_permission ->
    has_permission requires doc.owner == the acting user for a Private
    event). Whenever someone other than the owner saved the event - e.g.
    HQ/franchisor editing on a coach's behalf - that raised a
    PermissionError inside the save transaction, and appointments stopped
    saving entirely. Running the actual share in its own job after the
    transaction commits (enqueue_after_commit) means this can never block
    or break someone's save, no matter what goes wrong inside it.
    """
    try:
        frappe.enqueue(
            "dashboard.api.shared.calendar.share_event_with_admins_job",
            queue="short",
            timeout=60,
            enqueue_after_commit=True,
            event_name=doc.name,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Share Event with Admins - enqueue - {doc.name}")


def share_event_with_admins_job(event_name):
    """Background job body for share_event_with_admins() - see that docstring."""
    if not frappe.db.exists("Event", event_name):
        return

    for user in DASHBOARD_ADMIN_USERS:
        try:
            if not frappe.db.exists("User", user):
                continue
            # add_docshare (not the public share.add wrapper, which strips
            # flags for API safety) with ignore_share_permission=True: HQ/
            # office are always meant to see every appointment regardless of
            # who owns it, so this deliberately bypasses the ownership-based
            # share-permission check rather than depending on who happens to
            # be the acting user when the job runs. It already creates-or-
            # updates the DocShare itself, so there's no need to check for
            # an existing one first - doing so would also skip upgrading an
            # older read-only share to include write.
            frappe.share.add_docshare(
                "Event",
                event_name,
                user,
                read=1,
                write=1,
                notify=0,
                flags={"ignore_share_permission": True},
            )
            frappe.db.commit()
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Share Event with Admins - {event_name}")


def _can_modify_event(event_doc, dashboard_type, context):
    """
    Shared permission check for editing/deleting a session from the dashboard.
    A missing client (an appointment pulled in from Google Calendar, or an
    internal/personal entry like Holiday or Internal Training) is not the same
    as "belongs to someone else" - it just has no client-side detail attached.
    Falls back to direct ownership of the event itself in that case.
    """
    if context.get("is_dashboard_admin"):
        return True

    client = (event_doc.get("custom_client") or "").strip()

    if dashboard_type == SESSION_WORKER_DASHBOARD:
        if not client:
            return True
        return _client_belongs_to_session_worker(client, context)

    if dashboard_type == COACH_DASHBOARD:
        if not client:
            coach_name = (context.get("coach_name") or "").strip()
            if coach_name and (event_doc.get("custom_coach") or "").strip() == coach_name:
                return True
            return (event_doc.get("owner") or "") == context.get("user")
        client_row = _get_client_row(client)
        return bool(client_row) and _coach_can_view_client(client_row, context)

    # Franchisor dashboard: full oversight, no extra restriction.
    return True


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

def _get_google_calendar_for_booking(dashboard_type, context):
    user = context.get("view_as_user") or frappe.session.user

    if dashboard_type == SESSION_WORKER_DASHBOARD:
        worker_name = (context.get("worker_name") or "").strip()

        if worker_name and frappe.db.exists("Session Worker", worker_name):
            return frappe.db.get_value("Session Worker", worker_name, "google_calendar") or ""

    coach_name = (
        context.get("coach_name")
        or context.get("view_as_coach")
        or context.get("current_coach")
        or ""
    )

    if not coach_name:
        coach_name = frappe.db.get_value(
            "Coach",
            {"user": user},
            "name",
        ) or frappe.db.get_value(
            "Coach",
            {"email": user},
            "name",
        ) or ""

    if coach_name and frappe.db.exists("Coach", coach_name):
        return frappe.db.get_value("Coach", coach_name, "google_calendar") or ""

    return ""


def _google_calendar_has_token(google_calendar_name):
    if not google_calendar_name or not frappe.db.exists("Google Calendar", google_calendar_name):
        return False
    row = frappe.db.get_value("Google Calendar", google_calendar_name, ["refresh_token", "google_calendar_id"], as_dict=True) or {}
    token = (row.get("refresh_token") or "").strip()
    cal_id = (row.get("google_calendar_id") or "").strip()
    return bool(token and cal_id)


def _get_user_for_worker_value(worker_value, dashboard_type):
    if not worker_value or worker_value in (COACH_ME_VALUE, FRANCHISOR_ME_VALUE):
        return None
    if frappe.db.exists("DocType", "Session Worker") and frappe.db.exists("Session Worker", worker_value):
        return frappe.db.get_value("Session Worker", worker_value, "user") or None
    if frappe.db.exists("DocType", "Coach") and frappe.db.exists("Coach", worker_value):
        return frappe.db.get_value("Coach", worker_value, "user") or None
    return None


def _get_worker_name_for_user(user):
    if not user:
        return None
    if frappe.db.exists("DocType", "Session Worker"):
        name = frappe.db.get_value("Session Worker", {"user": user}, "name")
        if name:
            return name
    if frappe.db.exists("DocType", "Coach"):
        name = frappe.db.get_value("Coach", {"user": user}, "name")
        if name:
            return name
    return None


def _get_google_calendar_for_worker_user(user):
    if not user:
        return ""
    if frappe.db.exists("DocType", "Session Worker"):
        worker = frappe.db.get_value("Session Worker", {"user": user}, "name")
        if worker:
            return frappe.db.get_value("Session Worker", worker, "google_calendar") or ""
    if frappe.db.exists("DocType", "Coach"):
        coach = frappe.db.get_value("Coach", {"user": user}, "name")
        if coach:
            return frappe.db.get_value("Coach", coach, "google_calendar") or ""
    return ""


@frappe.whitelist(allow_guest=False)
def create_booking(
    client=None,
    client_name=None,
    parent_contact=None,
    lead_name=None,
    item_name=None,
    school=None,
    school_name=None,
    school_manual_name=None,
    booking_date=None,
    booking_time=None,
    from_date=None,
    to_date=None,
    duration_minutes=45,
    appointment_type="Therapy Session",
    location_type=None,
    location=None,
    phone=None,
    google_meet=None,
    notes=None,
    billing_type=None,
    travel_charged=None,
    recurring=None,
    recurring_frequency=None,
    recurring_count=None,
    additional_workers=None,
    dashboard_type=None,
):
    _require_logged_in_user()

    dashboard_type = _normalise_dashboard_type(dashboard_type)
    context = _get_context_for_dashboard(dashboard_type)

    client = _coalesce_str("client", client)
    client_name = _coalesce_str("client_name", client_name)
    parent_contact = _coalesce_str("parent_contact", parent_contact)
    lead_name = _coalesce_str("lead_name", lead_name)
    item_name = _coalesce_str("item_name", item_name)
    school = _coalesce_str("school", school)
    school_name = _coalesce_str("school_name", school_name)
    school_manual_name = _coalesce_str("school_manual_name", school_manual_name)
    booking_date = _coalesce_str("booking_date", booking_date)
    booking_time = _coalesce_str("booking_time", booking_time)
    from_date = _coalesce_str("from_date", from_date)
    to_date = _coalesce_str("to_date", to_date)
    appointment_type = _coalesce_str("appointment_type", appointment_type or "Therapy Session")
    location_type = _coalesce_str("location_type", location_type)
    location = _coalesce_str("location", location)
    phone = _coalesce_str("phone", phone)
    google_meet = _coalesce_raw("google_meet", google_meet)
    notes = _coalesce_str("notes", notes)
    billing_type = _coalesce_str("billing_type", billing_type)
    travel_charged = _coalesce_raw("travel_charged", travel_charged)
    duration_minutes = _coalesce_raw("duration_minutes", duration_minutes)
    recurring = _coalesce_raw("recurring", recurring)
    recurring_frequency = _coalesce_str("recurring_frequency", recurring_frequency)
    recurring_count = _coalesce_raw("recurring_count", recurring_count)

    if isinstance(additional_workers, str):
        import json as _json
        try:
            additional_workers = _json.loads(additional_workers)
        except Exception:
            additional_workers = []
    if not isinstance(additional_workers, list):
        additional_workers = []
    additional_workers = [w for w in additional_workers if isinstance(w, str) and w.strip()]

    if appointment_type not in CLIENT_SESSION_TYPES + NON_CLIENT_TYPES:
        frappe.throw(_("Invalid calendar item type."))

    try:
        duration_minutes = int(duration_minutes or 45)
    except Exception:
        duration_minutes = 45

    if duration_minutes <= 0:
        duration_minutes = 45

    if appointment_type in CLIENT_SESSION_TYPES:
        if not client:
            frappe.throw(_("Please select a client."))

        client_row = _can_book_or_edit_client(client, dashboard_type, context)

        if not client_name:
            client_name = _get_client_display_from_row(client_row)

    else:
        client_row = None

    if appointment_type == "Initial Consultation" and not lead_name:
        frappe.throw(_("Please enter the person's name."))

    if appointment_type in ["Internal Training", "Event / Stall", "Personal"] and not item_name:
        frappe.throw(_("Please enter a title."))

    if appointment_type in ("School Visit", "Company Meeting") and not school and not school_manual_name:
        frappe.throw(_("Please select a school / company or type the name."))

    if appointment_type == "Holiday":
        if not from_date or not to_date:
            frappe.throw(_("Please select the holiday dates."))

        start_dt = get_datetime(f"{from_date} 00:00:00")
        end_dt = get_datetime(f"{to_date} 23:59:00")
        repeat_count = 1
    else:
        if not booking_date or not booking_time:
            frappe.throw(_("Please select a booking date and time."))

        start_dt = get_datetime(f"{booking_date} {booking_time}:00")
        end_dt = add_to_date(start_dt, minutes=duration_minutes)

        try:
            repeat_count = int(recurring_count or 1)
        except Exception:
            repeat_count = 1

        if not _to_int(recurring):
            repeat_count = 1

        if appointment_type != "Therapy Session":
            repeat_count = 1

        if repeat_count not in [1, 4, 12]:
            repeat_count = 1

    # Validate every occurrence of a recurring booking for conflicts BEFORE
    # creating any of them. The loop below sets sync_with_google_calendar,
    # which triggers Frappe's own native Google Calendar sync synchronously
    # during each occurrence's own insert() - not a background job. If a
    # later occurrence in the same request then hit a conflict and threw,
    # the whole request's transaction rolled back (undoing the earlier
    # occurrences in Frappe), but their Google-side sync had already
    # happened for real and can't be undone by a database rollback - leaving
    # appointments in Google with no corresponding Frappe record at all.
    # Checking every date upfront means we never start creating anything if
    # any occurrence in the series would fail.
    for index in range(repeat_count):
        if not index:
            conflict_start, conflict_end = start_dt, end_dt
        elif recurring_frequency == "Fortnightly":
            conflict_start = add_to_date(start_dt, days=14 * index)
            conflict_end = add_to_date(end_dt, days=14 * index)
        elif recurring_frequency == "Monthly":
            conflict_start = add_to_date(start_dt, months=index)
            conflict_end = add_to_date(end_dt, months=index)
        else:
            conflict_start = add_to_date(start_dt, days=7 * index)
            conflict_end = add_to_date(end_dt, days=7 * index)

        conflict = _find_calendar_conflict(
            event_start=conflict_start,
            event_end=conflict_end,
            dashboard_type=dashboard_type,
            context=context,
        )

        if conflict:
            frappe.throw(_(
                "This calendar already has something booked at {0}: {1}"
            ).format(
                conflict_start.strftime("%d/%m/%Y %H:%M"),
                conflict.get("subject") or conflict.get("name"),
            ))

    created_events = []

    for index in range(repeat_count):
        event_start = start_dt
        event_end = end_dt

        if index:
            if recurring_frequency == "Fortnightly":
                event_start = add_to_date(start_dt, days=14 * index)
                event_end = add_to_date(end_dt, days=14 * index)
            elif recurring_frequency == "Monthly":
                event_start = add_to_date(start_dt, months=index)
                event_end = add_to_date(end_dt, months=index)
            else:
                event_start = add_to_date(start_dt, days=7 * index)
                event_end = add_to_date(end_dt, days=7 * index)

        conflict = _find_calendar_conflict(
            event_start=event_start,
            event_end=event_end,
            dashboard_type=dashboard_type,
            context=context,
        )

        if conflict:
            frappe.throw(_(
                "This calendar already has something booked at {0}: {1}"
            ).format(
                event_start.strftime("%d/%m/%Y %H:%M"),
                conflict.get("subject") or conflict.get("name"),
            ))

        event = frappe.new_doc("Event")
        google_calendar = _get_google_calendar_for_booking(
            dashboard_type=dashboard_type,
            context=context,
        )

        if google_calendar and _event_has_field("google_calendar") and _google_calendar_has_token(google_calendar):
            event.google_calendar = google_calendar
        calendar_owner = context.get("view_as_user") or frappe.session.user
        event.owner = calendar_owner

        if appointment_type == "Therapy Session":
            event.subject = f"{client_name} - Therapy Session"
        elif appointment_type == "Parent Check-In":
            event.subject = f"{client_name} - Parent Check-In"
        elif appointment_type == "Initial Consultation":
            event.subject = f"{lead_name} - Initial Consultation"
        elif appointment_type in ("School Visit", "Company Meeting"):
            event.subject = f"{school_name or school_manual_name or _get_client_display_name(school)} - {appointment_type}"
        elif appointment_type == "Holiday":
            event.subject = "Holiday"
        else:
            event.subject = f"{item_name} - {appointment_type}"

        event.starts_on = event_start
        event.ends_on = event_end

        if _event_has_field("event_type"):
            # "Private" restricts Frappe's own native visibility/reminders to the
            # owner (+ explicit participants). "Public" makes an Event visible and
            # reminder-eligible to *every* user per Frappe core's own permission
            # model - which is how every coach ended up seeing/being notified
            # about every other coach's appointments. The dashboard's own display
            # logic never reads this field (it always queries with
            # ignore_permissions=True), so this only affects Frappe's native side.
            event.event_type = "Private"

        if _event_has_field("sync_with_google_calendar") and event.get("google_calendar"):
            event.sync_with_google_calendar = 1

        if appointment_type in CLIENT_SESSION_TYPES and _event_has_field("custom_client"):
            event.custom_client = client

        if appointment_type in ("School Visit", "Company Meeting") and school and _event_has_field("custom_client"):
            event.custom_client = school

        _set_session_type(event, appointment_type)

        if _event_has_field("custom_billing_type"):
            event.custom_billing_type = billing_type or "Non-Billable"

        if _event_has_field("custom_appointment_status"):
            event.custom_appointment_status = "Scheduled"
        elif _event_has_field("appointment_status"):
            event.appointment_status = "Open"

        if _event_has_field("status"):
            event.status = "Open"

        if appointment_type in CLIENT_SESSION_TYPES:
            client_doc = frappe.get_doc("Client", client)
            therapy_location, therapy_location_text = _get_client_therapy_location(client_doc)

            if not location:
                location = therapy_location_text

            client_travel = _get_client_travel_defaults(client_doc)

            final_travel_charged = _to_int(
                travel_charged,
                default=int(client_travel.get("travel_charged") or 0),
            )

            if _event_has_field("custom_travel_charged"):
                event.custom_travel_charged = 1 if final_travel_charged else 0

            if _event_has_field("custom_travel_miles_one_way"):
                event.custom_travel_miles_one_way = float(client_travel.get("miles_one_way") or 0)

            if _event_has_field("custom_return_trip_required"):
                event.custom_return_trip_required = 1

            if _event_has_field("custom_session_worker") and client_row.get("session_worker"):
                event.custom_session_worker = client_row.get("session_worker")

            if _event_has_field("custom_therapy_location"):
                event.custom_therapy_location = therapy_location

        else:
            if _event_has_field("custom_travel_charged"):
                event.custom_travel_charged = 1 if _to_int(travel_charged) else 0

            if dashboard_type == SESSION_WORKER_DASHBOARD and _event_has_field("custom_session_worker"):
                worker_name = (context.get("worker_name") or "").strip()
                if worker_name:
                    event.custom_session_worker = worker_name

        if appointment_type in ("School Visit", "Company Meeting") and school:
            school_row = _get_client_row(school)
            if school_row and not location:
                location = _format_school_location(school_row)

        if _event_has_field("custom_total_travel_miles"):
            event.custom_total_travel_miles = _get_effective_total_travel_miles(event)

        if appointment_type == "Therapy Session" and repeat_count > 1:
            if _event_has_field("custom_session_number"):
                event.custom_session_number = index + 1

            if _event_has_field("custom_total_sessions"):
                event.custom_total_sessions = repeat_count

            if _event_has_field("custom_progress_text"):
                event.custom_progress_text = f"{index + 1} of {repeat_count}"

        final_notes = notes or ""

        if appointment_type == "Parent Check-In" and parent_contact:
            final_notes = f"Parent/contact: {parent_contact}\n\n{final_notes}".strip()

        if appointment_type == "Initial Consultation":
            lead = _create_or_update_initial_consultation_lead(
                lead_name=lead_name,
                phone=phone,
                notes=notes,
            )
            final_notes = f"Lead: {lead}\n\n{final_notes}".strip()

        if _to_int(google_meet):
            final_notes = "Google Meet required.\n\n" + final_notes

        if phone and appointment_type == "Initial Consultation":
            final_notes = f"Phone: {phone}\n\n{final_notes}".strip()

        if _event_has_field("location"):
            event.location = location

        if final_notes:
            event.description = final_notes

        event.insert(ignore_permissions=True)
        created_events.append(event)

    _ADDITIONAL_WORKER_TYPES = {"Internal Training", "Company Meeting", "School Visit", "Event / Stall"}
    if additional_workers and appointment_type in _ADDITIONAL_WORKER_TYPES and created_events:
        primary = created_events[0]
        for worker_value in additional_workers:
            worker_user = _get_user_for_worker_value(worker_value, dashboard_type)
            if not worker_user:
                continue
            worker_gc = _get_google_calendar_for_worker_user(worker_user)
            copy = frappe.new_doc("Event")
            copy.subject = primary.subject
            copy.starts_on = primary.starts_on
            copy.ends_on = primary.ends_on
            copy.owner = worker_user
            if _event_has_field("event_type"):
                copy.event_type = "Private"
            if worker_gc and _event_has_field("google_calendar") and _google_calendar_has_token(worker_gc):
                copy.google_calendar = worker_gc
            if _event_has_field("sync_with_google_calendar") and copy.get("google_calendar"):
                copy.sync_with_google_calendar = 1
            if _event_has_field("custom_appointment_type"):
                copy.custom_appointment_type = primary.get("custom_appointment_type") or appointment_type
            if _event_has_field("custom_billing_type"):
                copy.custom_billing_type = primary.get("custom_billing_type") or "Non-Billable"
            if _event_has_field("custom_appointment_status"):
                copy.custom_appointment_status = "Scheduled"
            elif _event_has_field("appointment_status"):
                copy.appointment_status = "Open"
            if _event_has_field("status"):
                copy.status = "Open"
            if _event_has_field("location") and primary.get("location"):
                copy.location = primary.location
            if _event_has_field("description") and primary.get("description"):
                copy.description = primary.description
            if _event_has_field("custom_session_worker"):
                worker_name = _get_worker_name_for_user(worker_user)
                if worker_name:
                    copy.custom_session_worker = worker_name
            copy.insert(ignore_permissions=True)

    return {
        "name": created_events[0].name if created_events else "",
        "title": created_events[0].subject if created_events else "",
        "count": len(created_events),
        "record_url": f"{_get_record_base_url(dashboard_type)}?event={created_events[0].name}" if created_events else "",
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
    link_client=None,
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

    if not _can_modify_event(event_doc, dashboard_type, context):
        frappe.throw(_("You do not have permission to update this session."), frappe.PermissionError)

    booking_date = _coalesce_str("booking_date", booking_date)
    booking_time = _coalesce_str("booking_time", booking_time)
    status = _coalesce_str("status", status)
    appointment_type = _coalesce_str("appointment_type", appointment_type)
    location = _coalesce_str("location", location)
    billing_type = _coalesce_str("billing_type", billing_type)
    travel_charged = _coalesce_raw("travel_charged", travel_charged)
    link_client = _coalesce_str("link_client", link_client)

    if link_client and not client and _event_has_field("custom_client"):
        if frappe.db.exists("Client", link_client):
            event_doc.custom_client = link_client
            client = link_client
            client_row = _get_client_row(client)

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
        event_doc.event_type = "Private"

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
def delete_session(event=None, dashboard_type=None):
    """
    Permanently remove an appointment from the calendar (coach, franchisor and
    session worker dashboards). If the event is synced with Google Calendar,
    deleting it here also removes/cancels it there via the coach_calendar_sync
    app's own on_trash hook - no separate Google cleanup needed here.
    """
    _require_logged_in_user()

    dashboard_type = _normalise_dashboard_type(dashboard_type)
    context = _get_context_for_dashboard(dashboard_type)

    event_name = _coalesce_str("event", event)
    if not event_name:
        frappe.throw(_("Event is required."))

    event_doc = frappe.get_doc("Event", event_name)

    if not _can_modify_event(event_doc, dashboard_type, context):
        frappe.throw(_("You do not have permission to delete this appointment."), frappe.PermissionError)

    # force=True: every synced appointment has Calendar Sync Log entries
    # linking back to it (one per push/pull attempt), and Frappe blocks
    # deleting a document that's still linked from elsewhere by default
    # ("Cannot delete or cancel because Event X is linked with Calendar Sync
    # Log Y"). Those logs are just historical diagnostics, not something
    # that needs to block deleting the appointment itself.
    frappe.delete_doc("Event", event_name, ignore_permissions=True, force=True)

    return {"deleted": event_name}


@frappe.whitelist(allow_guest=False)
def add_client_note(client=None, lead=None, session_date=None, session_type=None, notes=None, dashboard_type=None):
    _require_logged_in_user()

    dashboard_type = _normalise_dashboard_type(dashboard_type)
    context = _get_context_for_dashboard(dashboard_type)

    client = _coalesce_str("client", client)
    lead = _coalesce_str("lead", lead)
    session_type = _coalesce_str("session_type", session_type)
    notes = _coalesce_str("notes", notes)
    raw_session_date = _coalesce_raw("session_date", session_date)

    if not client and not lead:
        frappe.throw(_("Client is required."))

    if not notes:
        frappe.throw(_("Please enter a note."))

    if not raw_session_date:
        raw_session_date = getdate()

    if not session_type:
        session_type = "Other"

    # Initial Consultation appointments have a Lead, not a Client - notes go
    # on the Lead instead. A Lead isn't owned by a specific coach/worker the
    # way a Client is, so there's no equivalent ownership check here; access
    # to the lead id itself is already gated by only being reachable through
    # a specific appointment's own details, which the dashboard already
    # restricts to whoever can see that appointment.
    if not client and lead:
        if not frappe.db.exists("Lead", lead):
            frappe.throw(_("Selected lead was not found."))

        if not frappe.get_meta("Lead").has_field("notes"):
            frappe.throw(_(
                "Notes aren't set up for Leads on this site yet - ask your Frappe admin to "
                "add a Notes table field to the Lead doctype, the same way it exists on Client."
            ))

        return {
            "ok": True,
            "client_notes": _add_lead_note(lead, notes),
        }

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
