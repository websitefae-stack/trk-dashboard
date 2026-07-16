import random
import time

import frappe
from frappe import _
from frappe.utils import add_to_date, getdate, get_datetime, get_fullname, now_datetime
from dashboard.api.shared.session_worker_view_mode import get_session_worker_view_mode
from dashboard.api.shared.coach_view_mode import get_coach_view_mode
from dashboard.api.shared.utils import get_label as _get_label, get_request_payload as _get_request_payload, coalesce_raw as _coalesce_raw, coalesce_str as _coalesce_str, find_session_worker_for_user as _find_session_worker_for_user
from dashboard.api.shared.clients import build_display_name as _build_client_display_name
from dashboard.api.shared.email_templates import render_email, plain_text_to_email_html, parse_email_list, BOOKING_CONFIRMATION_TEMPLATE


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
NON_CLIENT_TYPES = ["Initial Consultation", "Internal Training", "School Visit", "Company Meeting", "School Session", "Company Session", "Event / Stall", "Holiday", "Personal"]
# Every appointment type except Holiday and Initial Consultation. Holiday
# isn't a single start time to begin with - it's already its own
# from_date/to_date range, so "recurring" doesn't map onto it the same way
# without a different UI entirely. Initial Consultation is a one-off
# meet-and-greet by nature, not something that repeats.
_RECURRING_EXCLUDED_TYPES = ("Holiday", "Initial Consultation")
RECURRING_ALLOWED_TYPES = CLIENT_SESSION_TYPES + [t for t in NON_CLIENT_TYPES if t not in _RECURRING_EXCLUDED_TYPES]
SCHOOL_LINKED_TYPES = ("School Visit", "Company Meeting", "School Session", "Company Session")
PACK_LINKED_SCHOOL_TYPES = ("School Session", "Company Session")


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
        "date_of_birth",
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
    is_admin = _is_dashboard_admin()

    context = {
        "user": user,
        "coach_name": None,
        "coach_label": fullname or user,
        "resolution_note": "",
        "is_dashboard_admin": is_admin,
    }

    if not frappe.db.exists("DocType", "Coach"):
        if is_admin:
            context["coach_label"] = "Dashboard Admin"
            context["resolution_note"] = "Dashboard admin access."
        else:
            context["resolution_note"] = "Could not find Coach DocType."
        return context

    meta = frappe.get_meta("Coach")
    fields = ["name"]

    label_fields = ["coach_name", "full_name", "employee_name", "user_full_name", "title", "name"]
    login_fields = ["user", "user_id", "email", "coach_email"]

    for fieldname in label_fields + login_fields:
        if meta.has_field(fieldname) and fieldname not in fields:
            fields.append(fieldname)

    # Resolve to the login's own Coach record first, even for a dashboard
    # admin - an admin who is *also* a working coach (e.g. Ashley) still
    # needs their own coach_name so their personal/Google-synced calendar
    # events (matched by custom_coach, not by admin status) show up. Only
    # fall back to "admin sees everything, no specific coach" once no
    # match is found.
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

    if is_admin:
        context["coach_label"] = "Dashboard Admin"
        context["resolution_note"] = "Dashboard admin access."
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


def _get_all_business_worker_rows():
    rows = []

    if frappe.db.exists("DocType", "Coach"):
        meta = frappe.get_meta("Coach")
        fields = ["name", "user"]

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
            rows.append({
                "value": COACH_PREFIX + coach.get("name"),
                "label": "Coach: " + _get_label(coach, ["coach_name", "full_name", "employee_name", "user_full_name", "title", "name"]),
                "user": coach.get("user"),
            })

    if frappe.db.exists("DocType", "Session Worker"):
        meta = frappe.get_meta("Session Worker")
        fields = ["name", "user"]

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
            rows.append({
                "value": WORKER_PREFIX + worker.get("name"),
                "label": "Session Worker: " + _get_label(worker, ["sw_name", "session_worker_name", "full_name", "employee_name", "user_full_name", "title", "name"]),
                "user": worker.get("user"),
            })

    return rows


def _get_franchisor_calendar_for_options():
    options = [{"value": FRANCHISOR_ME_VALUE, "label": "Me"}]
    options.extend({"value": row["value"], "label": row["label"]} for row in _get_all_business_worker_rows())
    return options


def _get_additional_worker_options(current_user=None):
    return [
        {"value": row["value"], "label": row["label"]}
        for row in _get_all_business_worker_rows()
        if not current_user or row.get("user") != current_user
    ]


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


def _get_clients_by_type_options(client_type):
    if not frappe.db.exists("DocType", "Client"):
        return []

    rows = frappe.get_all(
        "Client",
        fields=_get_client_base_fields(),
        filters={"client_type": client_type},
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


def _get_school_options():
    return _get_clients_by_type_options("School")


def _get_company_options():
    return _get_clients_by_type_options("Company")


def _get_effective_client_type(row):
    # The stored client_type field is only ever (re)computed when a Client
    # record is saved through code that calls apply_age_and_client_type() -
    # so any client created/edited before that logic existed can carry a
    # blank or stale value even though their date_of_birth is correct. Since
    # this drives whether Parent Check-In is offered at all, trust the DOB
    # (the real source of truth) over whatever's sitting in the field
    # whenever a DOB is available.
    from dashboard.api.shared.client_details import calculate_age_from_dob, get_client_type_from_age

    dob = row.get("date_of_birth")
    if dob:
        derived = get_client_type_from_age(calculate_age_from_dob(dob))
        if derived:
            return derived

    return row.get("client_type") or ""


def _build_client_option(row):
    return {
        "value": row.get("name"),
        "label": _get_client_display_from_row(row),
        "therapy_location": row.get("main_therapy_location") or "",
        "therapy_location_label": _get_client_therapy_location_label(row),
        "contacts": _get_client_contacts(row.get("name")),
        "client_type": _get_effective_client_type(row),
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

    if _event_has_field("custom_google_event_id"):
        fields.append("custom_google_event_id")

    if _event_has_field("custom_google_meet_url"):
        # Populated by the calendar sync app's real Google Calendar push
        # (see coach_calendar_sync/utils/google_calendar.py push_event()) -
        # the actual live Meet link, as opposed to google_meet_link above
        # which is this app's own, separate field and isn't kept in sync
        # with it.
        fields.append("custom_google_meet_url")

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


_DUPLICATE_BOOKING_WINDOW_MINUTES = 60


def _find_recent_duplicate_booking(event_start, owner_user, identity_text):
    """
    Catches a whole recurring series being submitted twice in a row - e.g.
    the coach isn't sure the first save actually went through (a slow
    multi-occurrence save, a confusing conflict prompt, a page reload) and
    resubmits the identical booking from scratch. Each submission passes
    its own upfront per-occurrence conflict check fine (it's checking
    against *other* appointments, not against itself), so nothing before
    this ever caught a person duplicating their own just-created series -
    that's how the same school visits kept turning up as two, sometimes
    three, complete sets of Events.

    Only looks at the very first occurrence's exact start time - if that
    matches something created moments ago by the same owner with a
    matching subject, the rest of the series is almost certainly the same
    resubmission, not worth checking occurrence-by-occurrence.
    """
    if not identity_text:
        return None

    cutoff = add_to_date(now_datetime(), minutes=-_DUPLICATE_BOOKING_WINDOW_MINUTES)

    rows = frappe.get_all(
        "Event",
        fields=["name", "subject"],
        filters=[
            ["Event", "starts_on", "=", event_start],
            ["Event", "owner", "=", owner_user],
            ["Event", "creation", ">=", cutoff],
        ],
        limit_page_length=5,
        ignore_permissions=True,
    )

    identity_text = identity_text.strip().lower()

    for row in rows:
        if identity_text in (row.get("subject") or "").strip().lower():
            return row

    return None


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
            "attachement": row.get("attachement") or "",
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
            has_coach_field = _event_has_field("custom_coach")
            coach_name = context.get("coach_name")

            by_name = {}

            owner_filters = base_filters + [
                ["Event", "owner", "=", owner_user],
            ]

            for row in frappe.get_all(
                "Event",
                fields=_get_event_fields(),
                filters=owner_filters,
                order_by="starts_on asc",
                limit_page_length=1000,
                ignore_permissions=True,
            ):
                by_name[row.get("name")] = row

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

            # Events pulled in from Google Calendar (personal appointments,
            # or anything with no linked client) are inserted by a
            # background sync job whose owner is never the coach's own
            # login - only custom_coach identifies them as this coach's.
            # Without this, they'd never show up here at all, even though
            # they exist in the Event doctype.
            if has_coach_field and coach_name:
                coach_filters = base_filters + [
                    ["Event", "custom_coach", "=", coach_name],
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

            # rows here are already scoped to this specific coach (owned by
            # them, linked to one of their own clients, or tagged with their
            # own custom_coach) - a client's default session_worker gets
            # auto-stamped onto every one of that client's bookings
            # regardless of who actually ran the session (see
            # _create_booking_impl), so excluding anything with a worker tag
            # was hiding real appointments (Parent Check-Ins especially)
            # that the coach genuinely owns.
            rows = sorted(by_name.values(), key=lambda row: row.get("starts_on") or "")

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

            # Same reasoning as the coach's own "Me" branch above - don't
            # exclude rows just because a worker tag got auto-stamped onto
            # them; they're already scoped to this specific coach.
            rows = sorted(by_name.values(), key=lambda row: row.get("starts_on") or "")
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

    # Frappe's own built-in Google Calendar integration independently pulls
    # the same pushed appointment back in as a second, blank Event once it
    # appears on the coach's Google Calendar. That shadow copy has no
    # custom_client and none of the session data - it's pure sync noise
    # sitting on top of the real, fully-populated native booking, so it
    # must never be shown as its own calendar entry.
    if row.get("google_calendar_event_id") and not custom_client:
        return None

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
        "google_meet_link": row.get("custom_google_meet_url") or row.get("google_meet_link") or "",
        "needs_linking": bool(
            (row.get("google_calendar_event_id") or row.get("custom_google_event_id"))
            and not custom_client
        ),
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

    if frappe.db.exists("DocType", "Pending Booking"):
        from dashboard.api.shared.pending_bookings import get_pending_bookings_for_calendar
        events.extend(
            get_pending_bookings_for_calendar(dashboard_type, context, range_start_date, range_end_date)
        )

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
        "companies": _get_company_options(),
        "additional_worker_options": _get_additional_worker_options(frappe.session.user),
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
            _get_lead_notes(lead) if lead else _get_event_notes(event_name)
        ),
        "session_number": int(event_doc.get("custom_session_number") or 0),
        "total_sessions": int(event_doc.get("custom_total_sessions") or 0),
        "progress_text": event_doc.get("custom_progress_text") or "",
        "booking_warning": event_doc.get("custom_booking_warning") or "",
        "google_meet_link": event_doc.get("custom_google_meet_url") or event_doc.get("google_meet_link") or "",
    }


def _booking_confirmation_context(event_doc, client):
    coach = event_doc.get("custom_coach") or ""
    coach_display_name = (frappe.db.get_value("Coach", coach, "coach_name") or coach) if coach else "Coach"

    starts_on = event_doc.get("starts_on")
    start_dt = get_datetime(starts_on) if starts_on else None

    return {
        "contact_name": _get_client_display_name(client),
        "appointment_type": event_doc.get("custom_appointment_type") or "",
        "coach_name": coach_display_name,
        "date": start_dt.strftime("%A %d %B %Y") if start_dt else "",
        "time": start_dt.strftime("%H:%M") if start_dt else "",
        "location_address": event_doc.get("location") or "",
    }


_BOOKING_CONFIRMATION_FALLBACK = (
    "Hi {{ contact_name }},\n"
    "\n"
    "Your {{ appointment_type }} with {{ coach_name }} is confirmed:\n"
    "\n"
    "{{ date }} at {{ time }}"
    "{% if location_address %}\n"
    "Location: {{ location_address }}{% endif %}\n"
    "\n"
    "We'll be in touch if anything changes. See you then!"
)


@frappe.whitelist()
def get_booking_confirmation_email_defaults(event=None):
    """
    Manual "send booking confirmation" flow for appointments a coach books
    directly (the automatic email only fires for guest public bookings) -
    the event is passed in explicitly by whichever specific appointment's
    Email button was clicked, so there's never any ambiguity about which
    booking it's for.
    """
    _require_logged_in_user()

    event = _coalesce_str("event", event)
    if not event:
        frappe.throw(_("Event is required."))

    event_doc = _get_event_doc(event)
    client = (event_doc.get("custom_client") or "").strip()

    if not client:
        frappe.throw(_("This appointment has no client linked, so there's no one to email."))

    context = _booking_confirmation_context(event_doc, client)

    subject, message = render_email(
        BOOKING_CONFIRMATION_TEMPLATE,
        context,
        fallback_subject="Your {{ appointment_type }} is confirmed",
        fallback_message=_BOOKING_CONFIRMATION_FALLBACK,
    )

    from dashboard.api.shared.invoices import get_client_email_options
    email_options = get_client_email_options(client_name=client)

    return {
        "subject": subject,
        "message": message,
        "recipient": email_options[0]["value"] if email_options else "",
        "email_options": email_options,
    }


@frappe.whitelist()
def send_booking_confirmation_email(event=None, recipient=None, subject=None, message=None, cc=None, sender=None):
    _require_logged_in_user()

    event = _coalesce_str("event", event)
    if not event:
        frappe.throw(_("Event is required."))

    recipient = (recipient or "").strip()
    if not recipient:
        frappe.throw(_("Recipient email is required."))

    event_doc = _get_event_doc(event)
    client = (event_doc.get("custom_client") or "").strip()

    if not client:
        frappe.throw(_("This appointment has no client linked, so there's no one to email."))

    subject = (subject or "Your appointment is confirmed").strip()
    message = plain_text_to_email_html((message or "").strip())

    kwargs = {
        "recipients": [recipient],
        "subject": subject,
        "message": message,
        "now": True,
        "reference_doctype": "Event",
        "reference_name": event,
    }

    cc_list = parse_email_list(cc)
    if cc_list:
        kwargs["cc"] = cc_list

    sender = (sender or "").strip()
    if sender:
        kwargs["sender"] = sender

    frappe.sendmail(**kwargs)

    return {"ok": 1}


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

def _get_user_for_worker_value(worker_value, dashboard_type):
    if not worker_value or worker_value in (COACH_ME_VALUE, FRANCHISOR_ME_VALUE):
        return None

    if worker_value.startswith(WORKER_PREFIX):
        worker_value = worker_value[len(WORKER_PREFIX):]
    elif worker_value.startswith(COACH_PREFIX):
        worker_value = worker_value[len(COACH_PREFIX):]

    if frappe.db.exists("DocType", "Session Worker") and frappe.db.exists("Session Worker", worker_value):
        return frappe.db.get_value("Session Worker", worker_value, "user") or None
    if frappe.db.exists("DocType", "Coach") and frappe.db.exists("Coach", worker_value):
        return frappe.db.get_value("Coach", worker_value, "user") or None
    return None


def _get_worker_doctype_and_name_for_user(user):
    """
    Returns (doctype, name) for whichever of Session Worker/Coach this user
    actually is. Callers must write the name to the Link field matching
    that doctype (custom_session_worker vs custom_coach) - a Coach's name
    written to a field that only links Session Worker records fails with
    a LinkValidationError at insert time.
    """
    if not user:
        return None, None
    if frappe.db.exists("DocType", "Session Worker"):
        name = frappe.db.get_value("Session Worker", {"user": user}, "name")
        if name:
            return "Session Worker", name
    if frappe.db.exists("DocType", "Coach"):
        name = frappe.db.get_value("Coach", {"user": user}, "name")
        if name:
            return "Coach", name
    return None, None


def compute_occurrence_window(index, start_dt, end_dt, recurring_frequency, duration_minutes, occurrence_overrides):
    """
    Shared date math for one occurrence of a (possibly recurring) booking.
    Used both by the live booking flow and by the pending-booking queue's
    conflict check, so the two can never drift out of sync with each other.
    """
    occurrence_overrides = occurrence_overrides or []

    # A coach can adjust individual occurrences of a recurring series before
    # saving (e.g. moving one session by a day) - when an override is
    # present for this occurrence, it wins outright over the weekly/
    # fortnightly/monthly formula.
    if index < len(occurrence_overrides):
        override = occurrence_overrides[index] or {}
        override_date = (override.get("date") or "").strip()
        override_time = (override.get("time") or "").strip()

        if override_date and override_time:
            occurrence_start = get_datetime(f"{override_date} {override_time}:00")
            occurrence_end = add_to_date(occurrence_start, minutes=duration_minutes)
            return occurrence_start, occurrence_end

    if not index:
        return start_dt, end_dt

    if recurring_frequency == "Fortnightly":
        return add_to_date(start_dt, days=14 * index), add_to_date(end_dt, days=14 * index)

    if recurring_frequency == "Monthly":
        return add_to_date(start_dt, months=index), add_to_date(end_dt, months=index)

    return add_to_date(start_dt, days=7 * index), add_to_date(end_dt, days=7 * index)


def _create_booking_impl(
    allow_double_booking=None,
    client=None,
    client_name=None,
    parent_contact=None,
    lead_name=None,
    client_lead=None,
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
    occurrence_overrides=None,
    additional_workers=None,
    dashboard_type=None,
):
    _require_logged_in_user()

    dashboard_type = _normalise_dashboard_type(dashboard_type)
    context = _get_context_for_dashboard(dashboard_type)

    if isinstance(occurrence_overrides, str):
        import json as _json
        try:
            occurrence_overrides = _json.loads(occurrence_overrides)
        except Exception:
            occurrence_overrides = []
    if not isinstance(occurrence_overrides, list):
        occurrence_overrides = []
    occurrence_overrides = [row if isinstance(row, dict) else {} for row in occurrence_overrides]

    client = _coalesce_str("client", client)
    client_name = _coalesce_str("client_name", client_name)
    parent_contact = _coalesce_str("parent_contact", parent_contact)
    lead_name = _coalesce_str("lead_name", lead_name)
    client_lead = _coalesce_str("client_lead", client_lead)
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
    allow_double_booking = _to_int(_coalesce_raw("allow_double_booking", allow_double_booking))
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

    if client_lead and not frappe.db.exists("Client Lead", client_lead):
        frappe.throw(_("Selected lead was not found."))

    if appointment_type in ["Internal Training", "Event / Stall", "Personal"] and not item_name:
        frappe.throw(_("Please enter a title."))

    if appointment_type in SCHOOL_LINKED_TYPES and not school and not school_manual_name:
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

        if appointment_type not in RECURRING_ALLOWED_TYPES:
            repeat_count = 1

        if repeat_count not in [1, 4, 12]:
            repeat_count = 1

    def _occurrence_window(index):
        return compute_occurrence_window(
            index, start_dt, end_dt, recurring_frequency, duration_minutes, occurrence_overrides
        )

    calendar_owner = context.get("view_as_user") or frappe.session.user

    # A resubmission of the exact same series looks, to the ordinary
    # conflict check below, like any other double-booking - and
    # allow_double_booking (clicking "Book Anyway" on that warning) was
    # letting people click straight through their own accidental
    # resubmission, silently creating a second full set of the same
    # recurring booking. This check is deliberately NOT affected by
    # allow_double_booking - unlike a genuine clash with an unrelated
    # appointment, "you already created this exact thing a moment ago"
    # should never be something a stray click bypasses.
    first_start, _first_end = _occurrence_window(0)
    duplicate_identity = (client_name or school_name or school_manual_name or item_name or lead_name or "").strip()
    duplicate = _find_recent_duplicate_booking(first_start, calendar_owner, duplicate_identity)
    if duplicate:
        frappe.throw(_(
            "This looks like it was already booked recently: {0} "
            "(starting {1}). If this isn't a duplicate, please wait a moment and try again."
        ).format(duplicate.get("subject") or duplicate.get("name"), first_start.strftime("%d/%m/%Y %H:%M")))

    # Validate every occurrence of a recurring booking for conflicts BEFORE
    # creating any of them, so a doomed series never partially creates
    # occurrences before failing on a later one.
    for index in range(repeat_count):
        conflict_start, conflict_end = _occurrence_window(index)

        conflict = _find_calendar_conflict(
            event_start=conflict_start,
            event_end=conflict_end,
            dashboard_type=dashboard_type,
            context=context,
        )

        if conflict and not allow_double_booking:
            frappe.throw(_(
                "This calendar already has something booked at {0}: {1}"
            ).format(
                conflict_start.strftime("%d/%m/%Y %H:%M"),
                conflict.get("subject") or conflict.get("name"),
            ))

    # Computed once rather than inside the loop below: the client doesn't
    # change between occurrences of the same recurring booking, so re-fetching
    # the Client doc and recalculating therapy location/travel defaults on
    # every single occurrence was pure repeated work for the same answer -
    # for a 12-occurrence monthly series that's 12 identical DB round trips,
    # extending how long the transaction (and the naming-series lock every
    # Event insert must briefly hold) stays open for no benefit.
    client_therapy_location = None
    client_therapy_location_text = None
    client_travel = None
    if appointment_type in CLIENT_SESSION_TYPES:
        client_doc_for_booking = frappe.get_doc("Client", client)
        client_therapy_location, client_therapy_location_text = _get_client_therapy_location(client_doc_for_booking)
        client_travel = _get_client_travel_defaults(client_doc_for_booking)

    # Same idea as above: Initial Consultation can now repeat too, and this
    # must only ever resolve to one Lead for the whole series, not a fresh
    # (or duplicate) one per occurrence.
    initial_consultation_lead = None

    created_events = []

    for index in range(repeat_count):
        event_start, event_end = _occurrence_window(index)

        conflict = _find_calendar_conflict(
            event_start=event_start,
            event_end=event_end,
            dashboard_type=dashboard_type,
            context=context,
        )

        if conflict and not allow_double_booking:
            frappe.throw(_(
                "This calendar already has something booked at {0}: {1}"
            ).format(
                event_start.strftime("%d/%m/%Y %H:%M"),
                conflict.get("subject") or conflict.get("name"),
            ))

        event = frappe.new_doc("Event")
        event.owner = calendar_owner

        # Types with no client attached (School Visit, Company Meeting,
        # Personal, etc) have nothing else tying them back to a coach - if
        # this ever gets saved by someone other than the coach themself
        # (office booking on their behalf, a background retry, ...), owner
        # alone won't find it again on that coach's own calendar. Stamp
        # custom_coach explicitly so every booking is attributable
        # regardless of who actually saves it.
        if dashboard_type == COACH_DASHBOARD and _event_has_field("custom_coach"):
            booking_coach_name = context.get("coach_name")
            if booking_coach_name:
                event.custom_coach = booking_coach_name

        if appointment_type == "Therapy Session":
            event.subject = f"{client_name} - Therapy Session"
        elif appointment_type == "Parent Check-In":
            event.subject = f"{client_name} - Parent Check-In"
        elif appointment_type == "Initial Consultation":
            event.subject = f"{lead_name} - Initial Consultation"
        elif appointment_type in SCHOOL_LINKED_TYPES:
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

        if appointment_type in CLIENT_SESSION_TYPES and _event_has_field("custom_client"):
            event.custom_client = client

        # Only School Session/Company Session are pack-billed against the
        # selected school/company - they need custom_client set so the
        # Package Booking Validation server script can find its balance.
        # School Visit/Company Meeting are plain non-billable org visits;
        # setting custom_client on them too made that same validation
        # script run its pack-balance checks on every one of them, which
        # both adds needless work to the save and risks a false "no
        # balance available" block on a booking that was never meant to
        # touch packages at all.
        if appointment_type in PACK_LINKED_SCHOOL_TYPES and school and _event_has_field("custom_client"):
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
            if not location:
                location = client_therapy_location_text

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
                event.custom_therapy_location = client_therapy_location

        else:
            if _event_has_field("custom_travel_charged"):
                event.custom_travel_charged = 1 if _to_int(travel_charged) else 0

            if dashboard_type == SESSION_WORKER_DASHBOARD and _event_has_field("custom_session_worker"):
                worker_name = (context.get("worker_name") or "").strip()
                if worker_name:
                    event.custom_session_worker = worker_name

        if appointment_type in SCHOOL_LINKED_TYPES and school:
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
            if initial_consultation_lead is None:
                initial_consultation_lead = _create_or_update_initial_consultation_lead(
                    lead_name=lead_name,
                    phone=phone,
                    notes=notes,
                )
            final_notes = f"Lead: {initial_consultation_lead}\n\n{final_notes}".strip()

            # Booked straight from the calendar (not via the Leads section's
            # "Book a Call" button, which already supplies client_lead) -
            # still needs to show up in the Leads section, so create one
            # here too. Only the person's name is known at this point, so
            # it's used for both contact and client - easy to split/correct
            # on the Lead's own detail page afterwards.
            if not client_lead:
                from dashboard.api.shared.leads import create_lead_from_booking

                booking_coach = frappe.db.get_value("Coach", {"user": calendar_owner}, "name") or \
                    frappe.db.get_value("Coach", {"coach_email": calendar_owner}, "name")

                client_lead = create_lead_from_booking(
                    contact_name=lead_name,
                    phone=phone,
                    coach=booking_coach,
                )

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

        # Real link field for bookings made from the Leads section, replacing
        # the "Lead: <name>" description-parsing trick used by the legacy
        # freeform Initial Consultation flow above (_get_lead_for_event()).
        if client_lead and appointment_type == "Initial Consultation" and index == 0:
            if _event_has_field("custom_client_lead"):
                frappe.db.set_value("Event", event.name, "custom_client_lead", client_lead)

            if frappe.get_meta("Client Lead").has_field("event"):
                frappe.db.set_value("Client Lead", client_lead, "event", event.name)

    _ADDITIONAL_WORKER_TYPES = {"Internal Training", "Company Meeting", "School Visit", "Event / Stall"}
    if additional_workers and appointment_type in _ADDITIONAL_WORKER_TYPES and created_events:
        for worker_value in additional_workers:
            worker_user = _get_user_for_worker_value(worker_value, dashboard_type)
            if not worker_user:
                continue
            worker_doctype, worker_name = _get_worker_doctype_and_name_for_user(worker_user)

            # A recurring booking has one entry in created_events per
            # occurrence - the additional worker needs a copy of every one
            # of them, not just the first, or their calendar ends up with
            # only the initial occurrence while the primary coach has all of
            # them.
            for primary in created_events:
                copy = frappe.new_doc("Event")
                copy.subject = primary.subject
                copy.starts_on = primary.starts_on
                copy.ends_on = primary.ends_on
                copy.owner = worker_user
                if _event_has_field("event_type"):
                    copy.event_type = "Private"
                _set_session_type(copy, appointment_type)
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
                if worker_doctype == "Session Worker" and worker_name and _event_has_field("custom_session_worker"):
                    copy.custom_session_worker = worker_name
                elif worker_doctype == "Coach" and worker_name and _event_has_field("custom_coach"):
                    copy.custom_coach = worker_name
                copy.insert(ignore_permissions=True)

    return {
        "name": created_events[0].name if created_events else "",
        "title": created_events[0].subject if created_events else "",
        "count": len(created_events),
        "record_url": f"{_get_record_base_url(dashboard_type)}?event={created_events[0].name}" if created_events else "",
    }


_BOOKING_LOCK_TIMEOUT_SECONDS = 5
_BOOKING_LOCK_MAX_ATTEMPTS = 3


def _is_lock_wait_timeout_error(exc):
    if type(exc).__name__ == "QueryTimeoutError":
        return True
    return "lock wait timeout" in str(exc).lower()


def _capture_lock_contention_diagnostics(exc):
    """
    Best-effort capture of what else MySQL was doing at the moment a booking
    hit the naming-series lock timeout, logged to the Error Log so it's
    visible without any bench/console/DB-admin access. Only called once
    retries are exhausted and the failure is about to be surfaced - the aim
    is to finally get real evidence of what's holding the row, since static
    code review hasn't turned up a synchronous culprit anywhere in this app.
    Silently logs whatever it could still read if the DB user lacks
    privilege for some of these views.
    """
    lines = [f"Original error: {exc}"]

    try:
        active_transactions = frappe.db.sql(
            """
            SELECT
                trx_id, trx_state, trx_started, trx_wait_started,
                trx_mysql_thread_id, trx_query, trx_rows_locked, trx_rows_modified
            FROM information_schema.innodb_trx
            ORDER BY trx_started ASC
            """,
            as_dict=True,
        )
        lines.append(f"Active InnoDB transactions at time of failure: {len(active_transactions)}")
        for row in active_transactions:
            lines.append(
                f"  thread={row.get('trx_mysql_thread_id')} state={row.get('trx_state')} "
                f"started={row.get('trx_started')} wait_started={row.get('trx_wait_started')} "
                f"rows_locked={row.get('trx_rows_locked')} rows_modified={row.get('trx_rows_modified')} "
                f"query={row.get('trx_query')}"
            )
    except Exception as diag_error:
        lines.append(f"Could not read information_schema.innodb_trx: {diag_error}")

    try:
        lock_waits = frappe.db.sql(
            "SELECT waiting_pid, waiting_query, blocking_pid, blocking_query FROM sys.innodb_lock_waits",
            as_dict=True,
        )
        lines.append(f"sys.innodb_lock_waits rows: {len(lock_waits)}")
        for row in lock_waits:
            lines.append(
                f"  waiting_pid={row.get('waiting_pid')} blocking_pid={row.get('blocking_pid')} "
                f"waiting_query={row.get('waiting_query')} blocking_query={row.get('blocking_query')}"
            )
    except Exception as diag_error:
        lines.append(f"Could not read sys.innodb_lock_waits: {diag_error}")

    frappe.log_error("\n".join(lines), "Booking Lock Contention Diagnostics")


@frappe.whitelist(allow_guest=False)
def create_booking(
    client=None,
    client_name=None,
    parent_contact=None,
    lead_name=None,
    client_lead=None,
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
    occurrence_overrides=None,
    additional_workers=None,
    dashboard_type=None,
    allow_double_booking=None,
):
    """
    Wrapper around _create_booking_impl() - see that function for the actual
    booking logic.

    Every new Event briefly contends for a single naming-series row shared
    by every Event on the site (Frappe's own design, not specific to this
    code). If some other transaction is holding that row at the moment a
    coach saves, MySQL's default lock wait is around 50 seconds - too long
    to make a coach wait on the offchance it clears, and too long to retry
    inline more than a couple of times.

    So this tries a couple of quick, short-timeout attempts first (the
    normal case - no contention - returns immediately, unchanged from
    before). If those still hit the same lock, instead of failing outright
    or making the coach keep waiting, the request is handed off to a
    background queue (pending_bookings.queue_booking) that keeps retrying
    for as long as it takes. Everything above the actual Event insert has
    already validated successfully by that point, so nothing needs
    re-checking - only the creation itself is deferred.
    """
    kwargs = dict(
        client=client,
        client_name=client_name,
        parent_contact=parent_contact,
        lead_name=lead_name,
        client_lead=client_lead,
        item_name=item_name,
        school=school,
        school_name=school_name,
        school_manual_name=school_manual_name,
        booking_date=booking_date,
        booking_time=booking_time,
        from_date=from_date,
        to_date=to_date,
        duration_minutes=duration_minutes,
        appointment_type=appointment_type,
        location_type=location_type,
        location=location,
        phone=phone,
        google_meet=google_meet,
        notes=notes,
        billing_type=billing_type,
        travel_charged=travel_charged,
        recurring=recurring,
        recurring_frequency=recurring_frequency,
        recurring_count=recurring_count,
        occurrence_overrides=occurrence_overrides,
        additional_workers=additional_workers,
        dashboard_type=dashboard_type,
        allow_double_booking=allow_double_booking,
    )

    try:
        frappe.db.sql(f"SET SESSION innodb_lock_wait_timeout = {_BOOKING_LOCK_TIMEOUT_SECONDS}")
    except Exception:
        pass

    for attempt in range(1, _BOOKING_LOCK_MAX_ATTEMPTS + 1):
        try:
            return _create_booking_impl(**kwargs)
        except Exception as e:
            if not _is_lock_wait_timeout_error(e):
                raise

            frappe.db.rollback()
            # A rolled-back attempt may already have marked background jobs
            # (Google push, HQ sharing, pack recalculation) as scheduled
            # against event names that no longer exist once we retry - clear
            # those per-request dedupe guards so the retry can enqueue them.
            frappe.local.flags.pop("coach_calendar_sync_scheduled_jobs", None)
            frappe.local.flags.pop("dashboard_recalc_balance_scheduled_jobs", None)

            if attempt == _BOOKING_LOCK_MAX_ATTEMPTS:
                # A couple of quick attempts weren't enough - rather than
                # keep the coach waiting on the offchance a longer wait
                # would clear it (or fail their booking outright), hand it
                # off to the background queue. Everything above this point
                # already validated successfully (that's the only way
                # execution reaches a lock timeout on the insert itself),
                # so nothing needs re-checking except the actual creation.
                _capture_lock_contention_diagnostics(e)
                from dashboard.api.shared.pending_bookings import queue_booking
                return queue_booking(kwargs, dashboard_type=dashboard_type)

            time.sleep(random.uniform(0.3, 0.8) * attempt)


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
def reschedule_event(event=None, date=None, dashboard_type=None):
    """
    Moves an appointment to a different day via drag-and-drop on the
    calendar grid, keeping its time-of-day and duration exactly as they
    were - deliberately narrower than update_session(), which defaults
    several other fields (status, billing type, ...) when they're not
    passed and would silently reset them on a plain drag-drop.
    """
    _require_logged_in_user()

    dashboard_type = _normalise_dashboard_type(dashboard_type)
    context = _get_context_for_dashboard(dashboard_type)

    event_name = _coalesce_str("event", event)
    date = _coalesce_str("date", date)

    if not event_name or not date:
        frappe.throw(_("Event and date are required."))

    event_doc = frappe.get_doc("Event", event_name)

    if not _can_modify_event(event_doc, dashboard_type, context):
        frappe.throw(_("You do not have permission to move this session."), frappe.PermissionError)

    if not event_doc.starts_on:
        frappe.throw(_("This session has no start time to move."))

    old_start = get_datetime(event_doc.starts_on)
    old_end = get_datetime(event_doc.ends_on) if event_doc.ends_on else None
    duration_minutes = max(int((old_end - old_start).total_seconds() / 60), 15) if old_end else 45

    new_start = get_datetime(f"{date} {old_start.strftime('%H:%M:%S')}")
    new_end = add_to_date(new_start, minutes=duration_minutes)

    if new_start == old_start:
        return {
            "name": event_doc.name,
            "date": old_start.strftime("%Y-%m-%d"),
            "start_time": old_start.strftime("%H:%M"),
            "end_time": old_end.strftime("%H:%M") if old_end else "",
        }

    conflict = frappe.get_all(
        "Event",
        filters=[
            ["name", "!=", event_doc.name],
            ["owner", "=", event_doc.owner],
            ["starts_on", "<", new_end],
            ["ends_on", ">", new_start],
        ],
        limit_page_length=1,
        ignore_permissions=True,
    )

    if conflict:
        frappe.throw(_("There's already a session booked at that time - drop it on a free day instead."))

    event_doc.starts_on = new_start
    event_doc.ends_on = new_end
    event_doc.save(ignore_permissions=True)

    return {
        "name": event_doc.name,
        "date": new_start.strftime("%Y-%m-%d"),
        "start_time": new_start.strftime("%H:%M"),
        "end_time": new_end.strftime("%H:%M"),
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


def _get_event_notes_parentfield():
    return _get_notes_parentfield("Event")


def _get_event_notes(event_name):
    return _get_notes_for_parent("Event", event_name)


@frappe.whitelist(allow_guest=False)
def add_client_note(client=None, lead=None, event=None, session_date=None, session_type=None, notes=None, attachement=None, dashboard_type=None):
    _require_logged_in_user()

    dashboard_type = _normalise_dashboard_type(dashboard_type)
    context = _get_context_for_dashboard(dashboard_type)

    client = _coalesce_str("client", client)
    lead = _coalesce_str("lead", lead)
    event = _coalesce_str("event", event)
    session_type = _coalesce_str("session_type", session_type)
    notes = _coalesce_str("notes", notes)
    attachement = _coalesce_str("attachement", attachement)
    raw_session_date = _coalesce_raw("session_date", session_date)

    if not client and not lead and not event:
        frappe.throw(_("Client is required."))

    if not notes:
        frappe.throw(_("Please enter a note."))

    if not raw_session_date:
        raw_session_date = getdate()

    if not session_type:
        session_type = "Other"

    # Some appointment types (Company Meeting, Internal Training, etc.) are
    # booked without a Client or Lead at all - save the note straight onto
    # the event's own Notes table instead of blocking it, the same shape
    # (date/user/notes/attachment) as Client/Lead notes.
    if not client and not lead and event:
        event_doc = _get_event_doc(event)
        parentfield = _get_event_notes_parentfield()

        if not parentfield:
            frappe.throw(_(
                "Notes aren't set up for Events on this site yet - ask your Frappe admin to "
                "add a Table field (options: Notes) to the Event doctype, the same way it "
                "exists on Client (session_notes)."
            ))

        new_note_row = {
            "doctype": "Notes",
            "session_date": raw_session_date,
            "session_type": session_type,
            "notes": notes,
        }

        if attachement and frappe.get_meta("Notes").has_field("attachement"):
            new_note_row["attachement"] = attachement

        event_doc.append(parentfield, new_note_row)
        event_doc.save(ignore_permissions=True)

        return {
            "ok": True,
            "client_notes": _get_event_notes(event),
        }

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
    new_note_row = {
        "doctype": "Notes",
        "client": client,
        "session_date": raw_session_date,
        "session_type": session_type,
        "notes": notes,
    }

    if attachement and frappe.get_meta("Notes").has_field("attachement"):
        new_note_row["attachement"] = attachement

    client_doc.append(parentfield, new_note_row)
    client_doc.save(ignore_permissions=True)

    return {
        "ok": True,
        "client_notes": _get_client_notes(client),
    }
