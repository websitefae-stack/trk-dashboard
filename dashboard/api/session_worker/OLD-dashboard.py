import frappe
from frappe import _
from frappe.utils import today, getdate, get_datetime, add_to_date

from dashboard.api.auth import (
    ensure_session_worker_role,
    get_session_worker_display_name,
    get_session_worker_doc,
    is_admin_like_user,
)

EVENT_DOCTYPE = "Event"
SESSION_STATUS_VALUES = ["Attended", "No Show", "Completed", "Closed"]
TRAVEL_STATUS_VALUES = ["Attended", "Completed"]

FREE_TRAVEL_MILES_ONE_WAY = 10
TRAVEL_EXCLUDED_SESSION_TYPES = ["Parent Check-In"]


def _event_has_field(fieldname):
    return frappe.get_meta(EVENT_DOCTYPE).has_field(fieldname)


def _get_month_label(date_value):
    return getdate(date_value).strftime("%B %Y")


def _get_week_label(start_date, end_date):
    return f"{getdate(start_date).strftime('%d %b %Y')} - {getdate(end_date).strftime('%d %b %Y')}"


def _get_current_week_range():
    base = getdate(today())
    days_from_sunday = (base.weekday() + 1) % 7
    start_date = add_to_date(base, days=-days_from_sunday)
    end_date = add_to_date(start_date, days=6)
    return getdate(start_date), getdate(end_date)


def _get_previous_week_range():
    current_start, _ = _get_current_week_range()
    previous_start = add_to_date(current_start, days=-7)
    previous_end = add_to_date(previous_start, days=6)
    return getdate(previous_start), getdate(previous_end)


def _get_current_month_range():
    base = getdate(today())
    start_date = base.replace(day=1)

    if base.month == 12:
        next_month = base.replace(year=base.year + 1, month=1, day=1)
    else:
        next_month = base.replace(month=base.month + 1, day=1)

    end_date = add_to_date(next_month, days=-1)
    return getdate(start_date), getdate(end_date)


def _get_previous_month_range():
    current_month_start, _ = _get_current_month_range()
    previous_month_end = add_to_date(current_month_start, days=-1)
    previous_month_start = previous_month_end.replace(day=1)
    return getdate(previous_month_start), getdate(previous_month_end)


def _get_biweekly_ranges(anchor_date):
    anchor = getdate(anchor_date)
    base = getdate(today())

    days_since_anchor = (base - anchor).days
    block_index = days_since_anchor // 14

    current_start = add_to_date(anchor, days=(block_index * 14))
    current_end = add_to_date(current_start, days=13)

    previous_start = add_to_date(current_start, days=-14)
    previous_end = add_to_date(current_start, days=-1)

    return (
        (getdate(current_start), getdate(current_end)),
        (getdate(previous_start), getdate(previous_end)),
    )


def _get_period_ranges(invoice_frequency, invoice_cycle_start_date=None):
    frequency = (invoice_frequency or "Monthly").strip()

    if frequency == "Weekly":
        current_start, current_end = _get_current_week_range()
        previous_start, previous_end = _get_previous_week_range()
        return {
            "current_start": current_start,
            "current_end": current_end,
            "previous_start": previous_start,
            "previous_end": previous_end,
            "current_label": _get_week_label(current_start, current_end),
            "previous_label": _get_week_label(previous_start, previous_end),
        }

    if frequency == "Bi-Weekly":
        if not invoice_cycle_start_date:
            frappe.throw(_("Please set Invoice Cycle Start Date for this Session Worker."))

        (current_start, current_end), (previous_start, previous_end) = _get_biweekly_ranges(invoice_cycle_start_date)
        return {
            "current_start": current_start,
            "current_end": current_end,
            "previous_start": previous_start,
            "previous_end": previous_end,
            "current_label": _get_week_label(current_start, current_end),
            "previous_label": _get_week_label(previous_start, previous_end),
        }

    current_start, current_end = _get_current_month_range()
    previous_start, previous_end = _get_previous_month_range()

    return {
        "current_start": current_start,
        "current_end": current_end,
        "previous_start": previous_start,
        "previous_end": previous_end,
        "current_label": _get_month_label(current_start),
        "previous_label": _get_month_label(previous_start),
    }


def _get_effective_session_type(row):
    value = (row.get("custom_session_type") or "").strip()
    if value:
        return value

    template_name = (row.get("custom_appointment_type") or "").strip()
    if template_name and frappe.db.exists("Appointment Template", template_name):
        template_doc = frappe.get_doc("Appointment Template", template_name)

        for fieldname in ["appointment_type", "title", "template_name", "name"]:
            template_value = (template_doc.get(fieldname) or "").strip()
            if template_value:
                return template_value

    return "General"


def _resolve_billing_type_from_session_type(session_type):
    session_type = (session_type or "").strip()
    if session_type == "General":
        return "Non-Billable"
    return "One to One"


def _get_effective_billing_type(row):
    billing_type = (row.get("custom_billing_type") or "").strip()
    if billing_type:
        return billing_type
    return _resolve_billing_type_from_session_type(_get_effective_session_type(row))


def _get_fallback_travel_miles_from_client(client_name):
    if not client_name or not frappe.db.exists("Client", client_name):
        return 0.0

    client_doc = frappe.get_doc("Client", client_name)

    travel_charged = (
        client_doc.get("travel_charged")
        or client_doc.get("custom_travel_charged")
        or client_doc.get("is_travel_charged")
        or 0
    )

    if not int(travel_charged or 0):
        return 0.0

    miles_one_way = (
        client_doc.get("travel_miles_one_way")
        or client_doc.get("custom_travel_miles_one_way")
        or 0
    )

    one_way = float(miles_one_way or 0)
    chargeable_one_way = max(one_way - FREE_TRAVEL_MILES_ONE_WAY, 0)

    return chargeable_one_way * 2


def _is_travel_excluded_session(row):
    session_type = (_get_effective_session_type(row) or "").strip()
    return session_type in TRAVEL_EXCLUDED_SESSION_TYPES


def _get_effective_total_travel_miles(row):
    if _is_travel_excluded_session(row):
        return 0.0

    if not int(row.get("custom_travel_charged") or 0):
        return 0.0

    client_name = row.get("custom_client")
    if client_name:
        return _get_fallback_travel_miles_from_client(client_name)

    one_way = float(row.get("custom_travel_miles_one_way") or 0)
    chargeable_one_way = max(one_way - FREE_TRAVEL_MILES_ONE_WAY, 0)

    return chargeable_one_way * 2


def _get_allowed_client_names(session_worker_name):
    if is_admin_like_user():
        return None

    if not session_worker_name:
        return []

    if not frappe.db.exists("DocType", "Client"):
        return []

    client_meta = frappe.get_meta("Client")
    if not client_meta.has_field("session_worker"):
        return []

    rows = frappe.get_all(
        "Client",
        filters={"session_worker": session_worker_name},
        fields=["name"],
        limit_page_length=10000,
    )
    return [row.name for row in rows if row.name]


def _get_event_filters(session_worker_name, start_date=None, end_date=None, future_only=False):
    filters = {}

    allowed_clients = _get_allowed_client_names(session_worker_name)

    if allowed_clients is not None:
        if not allowed_clients:
            return {"name": ["in", []]}
        if not _event_has_field("custom_client"):
            return {"name": ["in", []]}
        filters["custom_client"] = ["in", allowed_clients]

    if future_only:
        filters["starts_on"] = [">=", f"{today()} 00:00:00"]

    if start_date and end_date:
        filters["starts_on"] = ["between", [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]]

    return filters


def _count_billing_type(session_worker_name, wanted_billing_type, start_date, end_date):
    filters = _get_event_filters(session_worker_name, start_date, end_date)

    status_field = "custom_appointment_status" if _event_has_field("custom_appointment_status") else "status"
    filters[status_field] = ["in", SESSION_STATUS_VALUES]

    fields = ["name", "custom_billing_type", "custom_appointment_type"]
    if _event_has_field("custom_session_type"):
        fields.append("custom_session_type")

    rows = frappe.get_all(
        EVENT_DOCTYPE,
        filters=filters,
        fields=fields,
        limit_page_length=10000,
    )

    count = 0
    for row in rows:
        if _get_effective_billing_type(row) == wanted_billing_type:
            count += 1
    return count


def _sum_travel_miles(session_worker_name, start_date, end_date):
    filters = _get_event_filters(session_worker_name, start_date, end_date)

    status_field = "custom_appointment_status" if _event_has_field("custom_appointment_status") else "status"
    filters[status_field] = ["in", TRAVEL_STATUS_VALUES]

    fields = [
        "custom_client",
        "custom_travel_charged",
        "custom_travel_miles_one_way",
        "custom_return_trip_required",
        "custom_total_travel_miles",
        "custom_appointment_type",
        "custom_billing_type",
    ]

    if _event_has_field("custom_session_type"):
        fields.append("custom_session_type")

    rows = frappe.get_all(
        EVENT_DOCTYPE,
        filters=filters,
        fields=fields,
        limit_page_length=10000,
    )

    total = 0.0
    for row in rows:
        total += float(_get_effective_total_travel_miles(row) or 0)

    return total


def _get_client_display_name(client_name):
    if not client_name or not frappe.db.exists("Client", client_name):
        return client_name or "Session"

    client_doc = frappe.get_doc("Client", client_name)
    full_name = (client_doc.get("full_name") or "").strip()
    if full_name:
        return full_name

    first_name = (client_doc.get("first_name") or "").strip()
    last_name = (client_doc.get("last_name") or "").strip()
    display_name = " ".join([part for part in [first_name, last_name] if part]).strip()

    return display_name or client_doc.name


def _build_appointment_title(row):
    client_name = (row.get("custom_client") or "").strip()
    session_type = _get_effective_session_type(row)

    if client_name:
        return f"{_get_client_display_name(client_name)} - {session_type}"

    return (row.get("subject") or "Session").strip()


def _get_upcoming_appointments(session_worker_name, limit=8):
    filters = _get_event_filters(session_worker_name, future_only=True)

    if _event_has_field("custom_appointment_status"):
        filters["custom_appointment_status"] = "Scheduled"
    else:
        filters["status"] = "Open"

    fields = ["name", "subject", "starts_on", "ends_on", "custom_client", "custom_appointment_type"]
    if _event_has_field("custom_session_type"):
        fields.append("custom_session_type")

    rows = frappe.get_all(
        EVENT_DOCTYPE,
        filters=filters,
        fields=fields,
        order_by="starts_on asc",
        limit_page_length=limit,
    )

    appointments = []
    for row in rows:
        start_dt = get_datetime(row.get("starts_on")) if row.get("starts_on") else None

        appointments.append({
            "name": row.get("name"),
            "appointment_name": _build_appointment_title(row),
            "date": start_dt.strftime("%d %b %Y") if start_dt else "",
            "time": start_dt.strftime("%H:%M") if start_dt else "",
            "detail_link": f"/session_worker_db/calendar_details?event={row.get('name')}",
        })

    return appointments


@frappe.whitelist()
def get_dashboard_summary():
    ensure_session_worker_role()

    session_worker = get_session_worker_doc()
    session_worker_name = session_worker.name if session_worker else ""
    session_worker_display_name = get_session_worker_display_name()

    invoice_frequency = "Monthly"
    invoice_cycle_start_date = None

    if session_worker:
        meta = frappe.get_meta(session_worker.doctype)

        if meta.has_field("invoice_frequency"):
            invoice_frequency = (session_worker.get("invoice_frequency") or "Monthly").strip()

        if meta.has_field("invoice_cycle_start_date"):
            invoice_cycle_start_date = session_worker.get("invoice_cycle_start_date")

    period = _get_period_ranges(invoice_frequency, invoice_cycle_start_date)

    return {
        "session_worker_name": session_worker_display_name,
        "session_worker_docname": session_worker_name,
        "invoice_frequency": invoice_frequency,
        "previous_label": period["previous_label"],
        "current_label": period["current_label"],
        "one_to_one_previous": _count_billing_type(
            session_worker_name, "One to One", period["previous_start"], period["previous_end"]
        ),
        "one_to_one_current": _count_billing_type(
            session_worker_name, "One to One", period["current_start"], period["current_end"]
        ),
        "group_previous": _count_billing_type(
            session_worker_name, "Group", period["previous_start"], period["previous_end"]
        ),
        "group_current": _count_billing_type(
            session_worker_name, "Group", period["current_start"], period["current_end"]
        ),
        "workshop_previous": _count_billing_type(
            session_worker_name, "Workshop", period["previous_start"], period["previous_end"]
        ),
        "workshop_current": _count_billing_type(
            session_worker_name, "Workshop", period["current_start"], period["current_end"]
        ),
        "travel_miles_previous": _sum_travel_miles(
            session_worker_name, period["previous_start"], period["previous_end"]
        ),
        "travel_miles_current": _sum_travel_miles(
            session_worker_name, period["current_start"], period["current_end"]
        ),
        "upcoming_appointments": _get_upcoming_appointments(session_worker_name, limit=8),
    }
