import frappe
from frappe import _
from frappe.utils import today, getdate, get_datetime, add_to_date, flt, nowdate, get_fullname
from dashboard.api.shared.coach_view_mode import get_coach_view_mode
from dashboard.api.shared.session_worker_view_mode import get_session_worker_view_mode
from dashboard.api.shared import payment_utils
from dashboard.api.shared.utils import get_label as _get_label, get_request_payload as _get_request_payload, coalesce_raw as _coalesce_raw, coalesce_str as _coalesce_str, find_session_worker_for_user as _find_session_worker_for_user


DASHBOARD_ADMIN_USERS = [
    "ashley@theresilientkid.co.uk",
    "hq@theresilientkid.co.uk",
    "office@theresilienthub.co.uk",
]

SESSION_WORKER_DASHBOARD = "session_worker"
COACH_DASHBOARD = "coach"
FRANCHISOR_DASHBOARD = "franchisor"

EVENT_DOCTYPE = "Event"
SESSION_STATUS_VALUES = ["Attended", "No Show", "Completed", "Closed"]
TRAVEL_STATUS_VALUES = ["Attended", "Completed"]

FREE_TRAVEL_MILES_ONE_WAY = 10
TRAVEL_EXCLUDED_SESSION_TYPES = ["Parent Check-In"]
TRAVEL_ITEM_CODE = "TRA002"


# =========================================================
# GENERAL HELPERS
# =========================================================

def _require_logged_in_user():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    return frappe.session.user


def _is_dashboard_admin():
    return (frappe.session.user or "").strip().lower() in {
        email.lower() for email in DASHBOARD_ADMIN_USERS
    }


def _normalise_dashboard_type(dashboard_type=None):
    value = (dashboard_type or "").strip().lower()

    if value in [SESSION_WORKER_DASHBOARD, COACH_DASHBOARD, FRANCHISOR_DASHBOARD]:
        return value

    try:
        referrer = ""
        if getattr(frappe, "request", None):
            referrer = frappe.request.headers.get("Referer") or ""

        if "/coach_db" in referrer:
            return COACH_DASHBOARD
        if "/franchisor_db" in referrer:
            return FRANCHISOR_DASHBOARD
        if "/session_worker_db" in referrer:
            return SESSION_WORKER_DASHBOARD
    except Exception:
        pass

    return SESSION_WORKER_DASHBOARD


def _has_doctype(doctype):
    return frappe.db.exists("DocType", doctype)


def _has_field(doctype, fieldname):
    if not _has_doctype(doctype):
        return False

    return frappe.get_meta(doctype).has_field(fieldname)


def _event_has_field(fieldname):
    return _has_field(EVENT_DOCTYPE, fieldname)


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


def _get_period_ranges(invoice_frequency="Monthly", invoice_cycle_start_date=None):
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


# =========================================================
# USER / ROLE CONTEXT
# =========================================================


def _find_coach_for_user(user):
    if not _has_doctype("Coach"):
        return None

    fullname = (get_fullname(user) or "").strip()
    meta = frappe.get_meta("Coach")

    fields = ["name"]
    label_fields = ["coach_name", "full_name", "employee_name", "user_full_name", "title"]
    login_fields = ["user", "user_id", "email", "coach_email"]

    for fieldname in label_fields + login_fields:
        if meta.has_field(fieldname) and fieldname not in fields:
            fields.append(fieldname)

    for login_field in login_fields:
        if meta.has_field(login_field):
            row = frappe.db.get_value("Coach", {login_field: user}, fields, as_dict=True)
            if row:
                return {
                    "name": row.get("name"),
                    "label": _get_label(row, label_fields + ["name"]),
                }

    for label_field in label_fields:
        if fullname and meta.has_field(label_field):
            row = frappe.db.get_value("Coach", {label_field: fullname}, fields, as_dict=True)
            if row:
                return {
                    "name": row.get("name"),
                    "label": _get_label(row, label_fields + ["name"]),
                }

    return None


def _get_context_for_dashboard(dashboard_type):
    user = _require_logged_in_user()
    is_admin = _is_dashboard_admin()

    context = {
        "user": user,
        "user_label": get_fullname(user) or user,
        "dashboard_type": dashboard_type,
        "is_dashboard_admin": is_admin,
        "coach_name": None,
        "coach_label": "",
        "session_worker_name": None,
        "session_worker_label": "",
    }

    if dashboard_type == SESSION_WORKER_DASHBOARD:
        found_worker = _find_session_worker_for_user(user)
        if found_worker:
            context["session_worker_name"] = found_worker.get("name")
            context["session_worker_label"] = found_worker.get("label")

    if dashboard_type in (COACH_DASHBOARD, FRANCHISOR_DASHBOARD):
        # A franchisor-level login (e.g. Ashley, Emily) is very often also a
        # Coach in their own right - the dashboard home page's own summary
        # widgets need that identity to scope "their own" data, even though
        # franchisor admins otherwise see everything everywhere else.
        found_coach = _find_coach_for_user(user)
        if found_coach:
            context["coach_name"] = found_coach.get("name")
            context["coach_label"] = found_coach.get("label")

    return context


# =========================================================
# CLIENT HELPERS
# =========================================================

def _get_client_fields():
    if not _has_doctype("Client"):
        return []

    meta = frappe.get_meta("Client")
    wanted = [
        "name",
        "name1",
        "first_name",
        "last_name",
        "full_name",
        "preferred_name",
        "date_added",
        "primary_coach",
        "attending_coach",
        "session_worker",
        "company",
        "banking",
        "pricelist",
        "billing_contact",
        "status",
        "date_of_birth",
    ]

    fields = ["creation"]

    for fieldname in wanted:
        if fieldname == "name" or meta.has_field(fieldname):
            fields.append(fieldname)

    return fields


def _get_client_display(row):
    if not row:
        return ""

    for fieldname in ["full_name", "preferred_name"]:
        value = (row.get(fieldname) or "").strip()
        if value:
            return value

    first = (row.get("name1") or row.get("first_name") or "").strip()
    last = (row.get("last_name") or "").strip()

    display = " ".join([part for part in [first, last] if part]).strip()
    return display or row.get("name") or ""


def _get_client_row(client_name):
    if not client_name or not _has_doctype("Client"):
        return None

    fields = _get_client_fields()

    if not fields:
        return None

    return frappe.db.get_value("Client", client_name, fields, as_dict=True)


def _get_client_names_for_session_worker(context):
    if not _has_doctype("Client"):
        return []

    if context.get("is_dashboard_admin"):
        rows = frappe.get_all(
            "Client",
            fields=["name"],
            limit_page_length=10000,
            ignore_permissions=True,
        )
        return [row.name for row in rows]

    worker_name = context.get("session_worker_name")

    if not worker_name:
        return []

    rows = frappe.get_all(
        "Client",
        filters={"session_worker": worker_name},
        fields=["name"],
        limit_page_length=10000,
        ignore_permissions=True,
    )

    return [row.name for row in rows]


def _get_client_rows_for_coach_name(coach_name, primary_only=False):
    if not coach_name or not _has_doctype("Client"):
        return []

    rows_by_name = {}

    for row in frappe.get_all(
        "Client",
        fields=_get_client_fields(),
        filters={"primary_coach": coach_name},
        limit_page_length=10000,
        ignore_permissions=True,
    ):
        rows_by_name[row.name] = row

    if not primary_only:
        for row in frappe.get_all(
            "Client",
            fields=_get_client_fields(),
            filters={"attending_coach": coach_name},
            limit_page_length=10000,
            ignore_permissions=True,
        ):
            rows_by_name[row.name] = row

    return list(rows_by_name.values())


def _get_client_rows_for_coach(context, primary_only=False):
    if not _has_doctype("Client"):
        return []

    # A franchisor-level login who is ALSO a Coach (e.g. Ashley, Emily)
    # must always see their own coach dashboard scoped to their own
    # business, never every coach's - being a dashboard admin only matters
    # for logins with no coach identity of their own (e.g. a pure office
    # account), where there's nothing "own" to scope to and falling back to
    # everything is the only sensible default. The full, unscoped view
    # belongs on the other tabs (Clients, Invoices, etc.), not this summary.
    coach_name = context.get("coach_name")

    if coach_name:
        return _get_client_rows_for_coach_name(coach_name, primary_only=primary_only)

    if context.get("is_dashboard_admin"):
        return frappe.get_all(
            "Client",
            fields=_get_client_fields(),
            order_by="date_added desc",
            limit_page_length=10000,
            ignore_permissions=True,
        )

    return []


def _get_client_rows_for_franchisor():
    if not _has_doctype("Client"):
        return []

    return frappe.get_all(
        "Client",
        fields=_get_client_fields(),
        order_by="date_added desc",
        limit_page_length=10000,
        ignore_permissions=True,
    )


def _get_dashboard_client_rows(dashboard_type, context, primary_only_for_coach=False):
    if dashboard_type == SESSION_WORKER_DASHBOARD:
        client_names = _get_client_names_for_session_worker(context)
        rows = []

        for client_name in client_names:
            row = _get_client_row(client_name)
            if row:
                rows.append(row)

        return rows

    if dashboard_type in (COACH_DASHBOARD, FRANCHISOR_DASHBOARD):
        # Same helper for both - it already prefers the logged-in person's
        # own coach identity when one is resolvable (e.g. Ashley/Chantelle
        # viewing their own franchisor-accessible dashboard), only falling
        # back to every client for a login with no coach identity of its
        # own (e.g. a pure office account).
        return _get_client_rows_for_coach(context, primary_only=primary_only_for_coach)

    return []


def _count_clients_added(rows, start_date, end_date):
    # Based on the Client record's own creation date in Frappe, not the
    # (manually editable, sometimes stale/backfilled) date_added field.
    count = 0

    for row in rows:
        created_on = row.get("creation")
        if not created_on:
            continue

        created_on = getdate(created_on)

        if getdate(start_date) <= created_on <= getdate(end_date):
            count += 1

    return count


def _next_birthday(dob, from_date):
    """
    This year's (or next year's, if it's already passed) occurrence of the
    given date-of-birth's month/day. A 29 Feb birthday lands on 1 Mar in a
    non-leap year, matching how that's commonly observed.
    """
    for year in (from_date.year, from_date.year + 1):
        try:
            candidate = getdate(f"{year}-{dob.month:02d}-{dob.day:02d}")
        except Exception:
            if dob.month == 2 and dob.day == 29:
                candidate = getdate(f"{year}-03-01")
            else:
                continue

        if candidate >= from_date:
            return candidate

    return None


def _get_upcoming_birthdays(client_rows, days_ahead=14):
    today_date = getdate(nowdate())
    window_end = add_to_date(today_date, days=days_ahead)

    upcoming = []

    for row in client_rows:
        dob_value = row.get("date_of_birth")
        if not dob_value:
            continue

        dob = getdate(dob_value)
        next_birthday = _next_birthday(dob, today_date)

        if not next_birthday or next_birthday > window_end:
            continue

        upcoming.append({
            "client": row.get("name"),
            "client_label": _get_client_display(row) or row.get("name"),
            "date": next_birthday.strftime("%Y-%m-%d"),
            "turning_age": next_birthday.year - dob.year,
        })

    upcoming.sort(key=lambda item: item["date"])
    return upcoming


# =========================================================
# SESSION WORKER EXISTING SUMMARY HELPERS
# =========================================================

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
    client_row = _get_client_row(client_name)

    if not client_row:
        return 0.0

    travel_charged = client_row.get("travel_charged") or 0

    if not int(travel_charged or 0):
        return 0.0

    miles_one_way = client_row.get("travel_miles_one_way") or 0
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


def _get_event_filters_for_session_worker(context, start_date=None, end_date=None, future_only=False):
    filters = {}

    if not context.get("is_dashboard_admin"):
        worker_name = context.get("session_worker_name")

        if not worker_name:
            return {"name": ["in", []]}

        if _event_has_field("custom_session_worker"):
            filters["custom_session_worker"] = worker_name
        else:
            client_names = _get_client_names_for_session_worker(context)

            if not client_names:
                return {"name": ["in", []]}

            if not _event_has_field("custom_client"):
                return {"name": ["in", []]}

            filters["custom_client"] = ["in", client_names]

    if future_only:
        filters["starts_on"] = [">=", f"{today()} 00:00:00"]

    if start_date and end_date:
        filters["starts_on"] = ["between", [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]]

    return filters


def _count_billing_type(context, wanted_billing_type, start_date, end_date):
    filters = _get_event_filters_for_session_worker(context, start_date, end_date)

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
        ignore_permissions=True,
    )

    count = 0

    for row in rows:
        if _get_effective_billing_type(row) == wanted_billing_type:
            count += 1

    return count


def _sum_travel_miles(context, start_date, end_date):
    filters = _get_event_filters_for_session_worker(context, start_date, end_date)

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
        ignore_permissions=True,
    )

    total = 0.0

    for row in rows:
        total += float(_get_effective_total_travel_miles(row) or 0)

    return total


def _get_client_display_name(client_name):
    row = _get_client_row(client_name)
    return _get_client_display(row) if row else client_name or "Session"


def _build_appointment_title(row):
    client_name = (row.get("custom_client") or "").strip()
    session_type = _get_effective_session_type(row)

    if client_name:
        return f"{_get_client_display_name(client_name)} - {session_type}"

    return (row.get("subject") or "Session").strip()


def _get_upcoming_appointments(dashboard_type, context, limit=8):
    filters = {}

    if dashboard_type == SESSION_WORKER_DASHBOARD:
        filters = _get_event_filters_for_session_worker(context, future_only=True)

    elif dashboard_type == COACH_DASHBOARD:
        # Dashboard appointments must only be this coach user's own appointments.
        # Do NOT pull appointments through linked clients.
        filters["owner"] = context.get("view_as_user") or frappe.session.user
        filters["starts_on"] = [">=", f"{today()} 00:00:00"]

        if _event_has_field("custom_session_worker"):
            filters["custom_session_worker"] = ["in", ["", None]]

    elif dashboard_type == FRANCHISOR_DASHBOARD:
        coach_name = context.get("coach_name")

        if coach_name and _event_has_field("custom_coach"):
            # Scope the franchisor dashboard home page's Appointments widget
            # to the logged-in person's own coach identity (e.g. Ashley only
            # sees Ashley's own appointments, Emily only Emily's) rather than
            # every coach's - custom_coach is kept populated on every Event
            # (set directly on booking, or backfilled from owner by the
            # calendar sync app) so it's a more reliable "whose appointment
            # is this" signal than owner, which is just whoever happened to
            # be logged in when the booking was made.
            filters["custom_coach"] = coach_name
        else:
            # No specific coach identity for this login (e.g. a pure office
            # account) - fall back to their own bookings.
            filters["owner"] = context.get("view_as_user") or frappe.session.user

        filters["starts_on"] = [">=", f"{today()} 00:00:00"]

        if _event_has_field("custom_session_worker"):
            filters["custom_session_worker"] = ["in", ["", None]]

    else:
        return []

    if _event_has_field("custom_appointment_status"):
        filters["custom_appointment_status"] = "Scheduled"
    else:
        filters["status"] = "Open"

    fields = ["name", "subject", "starts_on", "ends_on", "location", "custom_client", "custom_appointment_type"]

    if _event_has_field("custom_session_type"):
        fields.append("custom_session_type")

    rows = frappe.get_all(
        EVENT_DOCTYPE,
        filters=filters,
        fields=fields,
        order_by="starts_on asc",
        limit_page_length=limit,
        ignore_permissions=True,
    )

    base_url = {
        SESSION_WORKER_DASHBOARD: "/session_worker_db/calendar_details",
        COACH_DASHBOARD: "/coach_db/calendar_details",
        FRANCHISOR_DASHBOARD: "/franchisor_db/calendar_details",
    }.get(dashboard_type, "/session_worker_db/calendar_details")

    appointments = []

    for row in rows:
        start_dt = get_datetime(row.get("starts_on")) if row.get("starts_on") else None

        appointments.append({
            "name": row.get("name"),
            "appointment_name": _build_appointment_title(row),
            "date": start_dt.strftime("%d-%m-%Y") if start_dt else "",
            "time": start_dt.strftime("%H:%M") if start_dt else "",
            "location": row.get("location") or "—",
            "detail_link": f"{base_url}?event={row.get('name')}",
        })

    return appointments


# =========================================================
# INVOICE HELPERS
# =========================================================

def _get_invoice_fields():
    return [
        "name",
        "custom_client",
        "customer",
        "customer_name",
        "company",
        "posting_date",
        "due_date",
        "status",
        "grand_total",
        "rounded_total",
        "outstanding_amount",
        "paid_amount",
        "currency",
        "debit_to",
        "docstatus",
    ]


def _get_invoice_client_names_for_dashboard(dashboard_type, context):
    if dashboard_type == COACH_DASHBOARD:
        # Invoices are based on the primary coach through Client.primary_coach.
        rows = _get_client_rows_for_coach(context, primary_only=True)
        return [row.name for row in rows if row.name]

    if dashboard_type == FRANCHISOR_DASHBOARD:
        # Prefers the logged-in person's own coach identity when one is
        # resolvable (e.g. Ashley/Chantelle only see their own revenue,
        # fees, YTD income, and outstanding invoices on their own home
        # page), only falling back to every client for a login with no
        # coach identity of its own (e.g. a pure office account). The full
        # Invoices list page is unaffected - it queries independently.
        coach_name = context.get("coach_name")
        if coach_name:
            rows = _get_client_rows_for_coach_name(coach_name, primary_only=True)
        else:
            rows = _get_client_rows_for_franchisor()
        return [row.name for row in rows if row.name]

    return []


def _get_invoice_filters(dashboard_type, context, start_date=None, end_date=None, outstanding_only=False):
    client_names = _get_invoice_client_names_for_dashboard(dashboard_type, context)

    or_conditions = []
    if client_names:
        or_conditions.append(["custom_client", "in", client_names])

    if dashboard_type == COACH_DASHBOARD:
        coach_name = context.get("coach_name")
        if coach_name and frappe.get_meta("Sales Invoice").has_field("custom_income_owner_coach"):
            # An invoice created with an overridden bank account (e.g. Emily
            # invoicing on SJ's behalf with her own account) is attributed to
            # the overriding coach via custom_income_owner_coach, even though
            # the client itself isn't otherwise assigned to that coach - it
            # still needs to count as that coach's own invoice/income.
            or_conditions.append(["custom_income_owner_coach", "=", coach_name])

    if not or_conditions:
        return {"name": ["in", []]}

    if len(or_conditions) == 1:
        field, operator, value = or_conditions[0]
        filters = {field: [operator, value]}
    else:
        matching_names = frappe.get_all(
            "Sales Invoice",
            or_filters=or_conditions,
            pluck="name",
            limit_page_length=100000,
            ignore_permissions=True,
        )
        filters = {"name": ["in", matching_names]}

    filters["docstatus"] = ["!=", 2]

    if start_date and end_date:
        filters["posting_date"] = ["between", [start_date, end_date]]

    if outstanding_only:
        filters["outstanding_amount"] = [">", 0]
        filters["status"] = ["in", ["Unpaid", "Overdue", "Partly Paid", "Unpaid and Discounted", "Partly Paid and Discounted", "Overdue and Discounted"]]

    return filters


def _sum_invoice_total(dashboard_type, context, start_date, end_date):
    filters = _get_invoice_filters(
        dashboard_type=dashboard_type,
        context=context,
        start_date=start_date,
        end_date=end_date,
        outstanding_only=False,
    )

    rows = frappe.get_all(
        "Sales Invoice",
        filters=filters,
        fields=["grand_total", "rounded_total"],
        limit_page_length=10000,
        ignore_permissions=True,
    )

    total = 0.0

    for row in rows:
        total += flt(row.get("grand_total") or row.get("rounded_total") or 0)

    return total


KIDS_TEENS_UNI_CLIENT_TYPES = {"Kid", "Teen", "Uni Student"}
SCHOOL_CLIENT_TYPES = {"School"}
PEOPLE_CLIENT_TYPES = {"Adult", "Company"}


def _get_invoice_revenue_breakdown(dashboard_type, context, start_date, end_date):
    """
    Splits the period's invoice total into:
    - client_total: ordinary client billing (kids_teens_uni_total +
      schools_total + people_total).
    - kids_teens_uni_total / schools_total / people_total: client_total
      further split by the invoiced Client's client_type - Kid/Teen/Uni
      Student, School, and Adult/Company respectively. Used by the
      franchisor dashboard's revenue breakdown and fee calculation (see
      _compute_fees - fees only apply to kids_teens_uni_total).
    - travel_total: the travel line items within that ordinary billing.
    - interbusiness_total: invoices raised against Franchise-type clients
      (coaches/HQ invoicing each other) - these must never be folded into
      the figure used to calculate franchisee fee/marketing invoices, since
      they're internal cross-charges rather than real client revenue.
    """
    filters = _get_invoice_filters(
        dashboard_type=dashboard_type,
        context=context,
        start_date=start_date,
        end_date=end_date,
        outstanding_only=False,
    )

    rows = frappe.get_all(
        "Sales Invoice",
        filters=filters,
        fields=["name", "custom_client", "grand_total", "rounded_total"],
        limit_page_length=10000,
        ignore_permissions=True,
    )

    empty = {
        "total": 0.0, "client_total": 0.0, "travel_total": 0.0, "interbusiness_total": 0.0,
        "kids_teens_uni_total": 0.0, "schools_total": 0.0, "people_total": 0.0,
    }

    if not rows:
        return empty

    invoice_names = [row.get("name") for row in rows if row.get("name")]
    client_names = list({row.get("custom_client") for row in rows if row.get("custom_client")})

    client_type_by_client = {}

    if client_names and frappe.db.has_column("Client", "client_type"):
        for client_row in frappe.get_all(
            "Client",
            filters={"name": ["in", client_names]},
            fields=["name", "client_type"],
            limit_page_length=len(client_names),
            ignore_permissions=True,
        ):
            client_type_by_client[client_row.get("name")] = client_row.get("client_type") or ""

    franchise_clients = {
        name for name, client_type in client_type_by_client.items() if client_type == "Franchise"
    }

    travel_by_invoice = {}

    if invoice_names:
        for row in frappe.get_all(
            "Sales Invoice Item",
            filters={"parent": ["in", invoice_names], "item_code": TRAVEL_ITEM_CODE},
            fields=["parent", "amount"],
            limit_page_length=100000,
            ignore_permissions=True,
        ):
            parent = row.get("parent")
            travel_by_invoice[parent] = travel_by_invoice.get(parent, 0.0) + flt(row.get("amount") or 0)

    total = 0.0
    travel_total = 0.0
    interbusiness_total = 0.0
    kids_teens_uni_total = 0.0
    schools_total = 0.0
    people_total = 0.0

    for row in rows:
        amount = flt(row.get("grand_total") or row.get("rounded_total") or 0)
        total += amount
        custom_client = row.get("custom_client")

        if custom_client in franchise_clients:
            interbusiness_total += amount
            continue

        travel_amount = travel_by_invoice.get(row.get("name"), 0.0)
        travel_total += travel_amount

        client_amount = amount - travel_amount
        client_type = client_type_by_client.get(custom_client, "")

        if client_type in SCHOOL_CLIENT_TYPES:
            schools_total += client_amount
        elif client_type in PEOPLE_CLIENT_TYPES:
            people_total += client_amount
        else:
            # Kid/Teen/Uni Student, and anything unrecognised (e.g. no
            # client_type set), default into this bucket rather than
            # silently vanishing from the client-type breakdown.
            kids_teens_uni_total += client_amount

    client_total = kids_teens_uni_total + schools_total + people_total

    return {
        "total": total,
        "client_total": client_total,
        "travel_total": travel_total,
        "interbusiness_total": interbusiness_total,
        "kids_teens_uni_total": kids_teens_uni_total,
        "schools_total": schools_total,
        "people_total": people_total,
    }


MARKETING_FEE_RATE = 0.02

# (ceiling, rate) - the first tier whose ceiling the gross revenue doesn't
# exceed applies. "Up to £1,500" and "Between £1,500 - £2,999" both name
# exactly £1,500 in the source table; treated here as belonging to the
# first (lower) tier, matching the more natural reading of "up to".
FRANCHISE_FEE_TIERS = [
    (1500, 0.10),
    (2999.99, 0.08),
]
FRANCHISE_FEE_DEFAULT_RATE = 0.07  # £3,000+

# The franchise fee is always at least this, even on a £0 revenue month -
# it's a standing due, not just a percentage of activity. In practice this
# means anything up to £1,000 gross revenue (where 10% would be under
# £100) is charged the flat £100 instead; above that, the normal tiered
# percentage applies and naturally exceeds it.
FRANCHISE_FEE_MINIMUM = 100


def _franchise_fee_rate(gross_revenue):
    for ceiling, rate in FRANCHISE_FEE_TIERS:
        if gross_revenue <= ceiling:
            return rate

    return FRANCHISE_FEE_DEFAULT_RATE


def _compute_fees(revenue_breakdown, dashboard_type=None):
    """
    Marketing fee: 2% of the fee-eligible client revenue. Franchise fee: a
    tiered percentage of Gross Revenue (fee-eligible client revenue +
    Travel) - interbusiness cross-charges are never counted (see
    _get_invoice_revenue_breakdown's own docstring) - with a £100 minimum
    that always applies, including a £0 revenue period.

    On the franchisor dashboard, "fee-eligible" is Kids/Teens/Uni Student
    revenue only - Ashley currently only pays fees on that segment, not on
    Schools or People (Adult/Company) invoicing. Every other dashboard
    keeps the old behaviour of fees applying to all client revenue.
    """
    if dashboard_type == FRANCHISOR_DASHBOARD:
        fee_eligible_total = flt(revenue_breakdown.get("kids_teens_uni_total"))
    else:
        fee_eligible_total = flt(revenue_breakdown.get("client_total"))

    travel_total = flt(revenue_breakdown.get("travel_total"))

    gross_revenue = fee_eligible_total + travel_total
    franchise_fee_rate = _franchise_fee_rate(gross_revenue)
    franchise_fee = max(gross_revenue * franchise_fee_rate, FRANCHISE_FEE_MINIMUM)

    return {
        "gross_revenue": gross_revenue,
        "marketing_fee": fee_eligible_total * MARKETING_FEE_RATE,
        "franchise_fee": franchise_fee,
        "franchise_fee_rate": franchise_fee_rate,
    }


def _sum_invoice_total_ytd(dashboard_type, context):
    current_year = getdate(today()).year
    start_date = getdate(f"{current_year}-01-01")
    end_date = getdate(today())

    return _sum_invoice_total(
        dashboard_type,
        context,
        start_date,
        end_date,
    )


def _get_outstanding_invoices(dashboard_type, context, limit=8):
    filters = _get_invoice_filters(
        dashboard_type=dashboard_type,
        context=context,
        outstanding_only=True,
    )

    rows = frappe.get_all(
        "Sales Invoice",
        filters=filters,
        fields=_get_invoice_fields(),
        order_by="posting_date desc",
        limit_page_length=limit,
        ignore_permissions=True,
    )

    invoices = []

    for row in rows:
        client_row = _get_client_row(row.get("custom_client"))
        client_name = _get_client_display(client_row) if client_row else row.get("customer_name") or row.get("customer")

        outstanding_amount = payment_utils.get_outstanding_amount_for_payment(
            row.get("outstanding_amount"),
            row.get("grand_total") or row.get("rounded_total"),
            row.get("name"),
        )

        base_url = {
            COACH_DASHBOARD: "/coach_db/invoice_details",
            FRANCHISOR_DASHBOARD: "/franchisor_db/invoice_details",
        }.get(dashboard_type, "/coach_db/invoice_details")

        invoices.append({
            "name": row.get("name"),
            "client": row.get("custom_client"),
            "client_name": client_name,
            "customer": row.get("customer"),
            "posting_date": str(row.get("posting_date") or ""),
            "due_date": str(row.get("due_date") or ""),
            "status": row.get("status") or "",
            "grand_total": flt(row.get("grand_total") or row.get("rounded_total") or 0),
            "outstanding_amount": outstanding_amount,
            "currency": row.get("currency") or "GBP",
            "invoice_url": f"{base_url}?name={row.get('name')}",
        })

    return invoices


def _get_outstanding_internal_invoices(dashboard_type, context, limit=8):
    """
    Invoices raised against a Coach's own linked Client record (e.g. HQ
    invoicing a coach for fees) that are still outstanding.

    On the coach dashboard this is just their own - the invoices they
    personally owe. Invoices owed *to* a coach live in the ordinary
    Outstanding Invoices section instead, never here.

    On the franchisor dashboard this always covers every coach with a
    linked Client (every login sees the full "owed to office" picture,
    including their own fees if they're also a coach) - this is the
    office/bookkeeping view used to mark coaches' fee invoices paid, so it
    deliberately does NOT narrow to only the logged-in franchisor's own
    invoices the way revenue/fees/YTD income elsewhere on this page does.
    """
    if not _has_doctype("Coach") or not frappe.get_meta("Coach").has_field("linked_client"):
        return []

    if dashboard_type == COACH_DASHBOARD:
        coach_name = context.get("coach_name")
        if not coach_name:
            return []

        linked_client = frappe.db.get_value("Coach", coach_name, "linked_client")
        client_to_coach = {linked_client: coach_name} if linked_client else {}

    elif dashboard_type == FRANCHISOR_DASHBOARD:
        coach_rows = frappe.get_all(
            "Coach",
            filters={"linked_client": ["is", "set"]},
            fields=["name", "linked_client"],
            limit_page_length=1000,
            ignore_permissions=True,
        )
        client_to_coach = {row.linked_client: row.name for row in coach_rows if row.linked_client}

    else:
        return []

    client_names = list(client_to_coach.keys())

    if not client_names:
        return []

    rows = frappe.get_all(
        "Sales Invoice",
        filters={
            "custom_client": ["in", client_names],
            "docstatus": 1,
            "outstanding_amount": [">", 0],
        },
        fields=[
            "name", "custom_client", "posting_date", "due_date",
            "status", "grand_total", "rounded_total", "outstanding_amount", "currency",
        ],
        order_by="posting_date desc",
        limit_page_length=limit,
        ignore_permissions=True,
    )

    base_url = {
        COACH_DASHBOARD: "/coach_db/invoice_details",
        FRANCHISOR_DASHBOARD: "/franchisor_db/invoice_details",
    }.get(dashboard_type, "/coach_db/invoice_details")

    invoices = []

    for row in rows:
        coach_name = client_to_coach.get(row.get("custom_client")) or ""
        coach_label = (
            frappe.db.get_value("Coach", coach_name, "coach_name") or coach_name
        ) if coach_name else ""

        invoices.append({
            "name": row.get("name"),
            "coach": coach_name,
            "coach_label": coach_label,
            "posting_date": str(row.get("posting_date") or ""),
            "due_date": str(row.get("due_date") or ""),
            "status": row.get("status") or "",
            "grand_total": flt(row.get("grand_total") or row.get("rounded_total") or 0),
            "outstanding_amount": flt(row.get("outstanding_amount") or 0),
            "currency": row.get("currency") or "GBP",
            "invoice_url": f"{base_url}?name={row.get('name')}",
        })

    return invoices


def _user_can_access_invoice(invoice_name, dashboard_type, context):
    row = frappe.db.get_value(
        "Sales Invoice",
        invoice_name,
        ["name", "custom_client"],
        as_dict=True,
    )

    if not row:
        return False

    if dashboard_type == FRANCHISOR_DASHBOARD:
        return True

    if dashboard_type != COACH_DASHBOARD:
        return False

    client_row = _get_client_row(row.get("custom_client"))

    if not client_row:
        return False

    if context.get("is_dashboard_admin"):
        return True

    coach_name = (context.get("coach_name") or "").strip()

    # An "internal invoice" (HQ invoicing a coach for their own fees) is
    # raised against Coach.linked_client - the coach it's about needs to be
    # able to open it regardless of how that Client record's client_type or
    # primary_coach happen to be set up, since those are independent of the
    # actual invoice-owner relationship (see _get_outstanding_internal_invoices).
    if coach_name and frappe.get_meta("Coach").has_field("linked_client"):
        own_linked_client = frappe.db.get_value("Coach", coach_name, "linked_client")
        if own_linked_client and own_linked_client == row.get("custom_client"):
            return True

    # Franchise-type clients represent coaches themselves (for cross-coach/
    # HQ invoicing) and aren't tied to a specific primary/attending coach -
    # every coach needs access regardless of assignment.
    client_type = frappe.db.get_value("Client", row.get("custom_client"), "client_type")
    if client_type == "Franchise":
        return True

    return (client_row.get("primary_coach") or "").strip() == coach_name


def _resolve_paid_to_account(invoice_doc, client_row):
    # An invoice-specific bank account override (e.g. Emily invoicing on
    # SJ's behalf with her own account) takes priority over the client's
    # own default - see the matching logic in invoices.allocate_invoice_payment.
    bank_account = ""

    if invoice_doc.meta.has_field("custom_bank_account") and invoice_doc.get("custom_bank_account"):
        bank_account = invoice_doc.get("custom_bank_account")
    elif client_row:
        bank_account = client_row.get("banking") or ""

    if not bank_account or not frappe.db.exists("Bank Account", bank_account):
        return ""

    bank_meta = frappe.get_meta("Bank Account")

    for fieldname in ["account", "account_name"]:
        if bank_meta.has_field(fieldname):
            value = frappe.db.get_value("Bank Account", bank_account, fieldname)
            if value and frappe.db.exists("Account", value):
                return value

    return ""


@frappe.whitelist()
def mark_invoice_paid(invoice=None, payment_date=None, dashboard_type=None, amount_paid=None):
    user = _require_logged_in_user()
    dashboard_type = _normalise_dashboard_type(dashboard_type)
    context = _get_context_for_dashboard(dashboard_type)

    invoice = _coalesce_str("invoice", invoice)
    payment_date = _coalesce_str("payment_date", payment_date) or today()
    amount_paid = _coalesce_str("amount_paid", amount_paid)

    if not invoice:
        frappe.throw(_("Please select an invoice."))

    if not _user_can_access_invoice(invoice, dashboard_type, context):
        frappe.throw(_("You do not have permission to mark this invoice as paid."), frappe.PermissionError)

    invoice_doc = frappe.get_doc("Sales Invoice", invoice)

    if invoice_doc.docstatus != 1:
        frappe.throw(_("Only submitted Sales Invoices can be marked as paid."))

    outstanding_amount = payment_utils.get_outstanding_amount_for_payment(
        invoice_doc.outstanding_amount, invoice_doc.grand_total, invoice
    )

    if outstanding_amount <= 0:
        return {
            "ok": True,
            "message": "Invoice is already paid.",
            "invoice": invoice,
        }

    final_amount = flt(amount_paid, 2) if amount_paid else outstanding_amount

    if final_amount <= 0:
        frappe.throw(_("Amount paid must be greater than zero."))

    if final_amount > outstanding_amount:
        frappe.throw(_("Amount paid cannot be greater than the outstanding amount ({0})").format(outstanding_amount))

    client_row = _get_client_row(invoice_doc.get("custom_client"))

    paid_to = _resolve_paid_to_account(invoice_doc, client_row)

    if not paid_to:
        frappe.throw(_("No valid Bank Account ledger account was found from the Client banking field."))

    if not invoice_doc.customer:
        frappe.throw(_("No customer found for this invoice."))

    payment_entry = payment_utils.build_and_submit_payment_entry(
        invoice_name=invoice,
        paid_to_account=paid_to,
        payment_date=payment_date,
        remarks=f"Payment marked as paid from dashboard by {user}",
        final_amount=final_amount,
    )

    is_partial = final_amount < outstanding_amount

    return {
        "ok": True,
        "message": "Partial payment recorded." if is_partial else "Payment Entry created.",
        "invoice": invoice,
        "payment_entry": payment_entry.name,
    }


@frappe.whitelist()
def run_invoice_rounding_selftest(reference_invoice=None, test_amount=439.20, confirm=0):
    """
    Admin-only, self-cleaning diagnostic. Clones reference_invoice's
    customer/company/bank/item setup into a brand new test Sales Invoice
    for test_amount, submits it, records the GL Entries and Payment
    Ledger Entries ERPNext actually posted for it, pays it in full
    through the exact same code path real users go through
    (payment_utils.build_and_submit_payment_entry), and reports success
    or failure with full diagnostic detail - then cancels and deletes
    every test document it created, regardless of outcome.

    Requires confirm=1 (this creates and cancels real accounting
    documents on this site) and the System Manager role.
    """
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Not permitted."), frappe.PermissionError)

    if not int(confirm or 0):
        frappe.throw(_("Pass confirm=1 to run this - it creates and cancels a real Sales Invoice and Payment Entry."))

    reference_invoice = _coalesce_str("reference_invoice", reference_invoice)

    if not reference_invoice or not frappe.db.exists("Sales Invoice", reference_invoice):
        frappe.throw(_("Please provide a valid reference_invoice name to clone the customer/company/bank setup from."))

    test_amount = flt(test_amount or 439.20, 2)
    ref_doc = frappe.get_doc("Sales Invoice", reference_invoice)

    report = {
        "reference_invoice": reference_invoice,
        "reference_invoice_totals": {
            "grand_total": ref_doc.grand_total,
            "rounded_total": ref_doc.rounded_total,
            "outstanding_amount": ref_doc.outstanding_amount,
            "rounding_adjustment": ref_doc.rounding_adjustment,
            "disable_rounded_total": ref_doc.get("disable_rounded_total"),
        },
        "reference_gl_entries": payment_utils.dump_gl_entries(reference_invoice),
        "reference_payment_ledger_entries": payment_utils.dump_payment_ledger_entries(reference_invoice),
    }

    test_invoice_name = None
    test_payment_name = None

    try:
        test_doc = frappe.new_doc("Sales Invoice")
        test_doc.customer = ref_doc.customer
        test_doc.company = ref_doc.company
        test_doc.posting_date = nowdate()
        test_doc.due_date = nowdate()

        if test_doc.meta.has_field("custom_client"):
            test_doc.custom_client = ref_doc.get("custom_client")

        if test_doc.meta.has_field("custom_bank_account"):
            test_doc.custom_bank_account = ref_doc.get("custom_bank_account")

        if test_doc.meta.has_field("custom_income_owner_coach"):
            test_doc.custom_income_owner_coach = ref_doc.get("custom_income_owner_coach")

        if test_doc.meta.has_field("disable_rounded_total"):
            test_doc.disable_rounded_total = 1
            test_doc.rounding_adjustment = 0
            test_doc.base_rounding_adjustment = 0

        first_item = ref_doc.items[0]
        test_doc.append("items", {
            "item_code": first_item.item_code,
            "qty": 1,
            "rate": test_amount,
        })

        test_doc.insert(ignore_permissions=True)
        test_doc.submit()
        test_invoice_name = test_doc.name

        report["test_invoice"] = test_invoice_name
        report["test_invoice_totals"] = {
            "grand_total": test_doc.grand_total,
            "rounded_total": test_doc.rounded_total,
            "outstanding_amount": test_doc.outstanding_amount,
            "rounding_adjustment": test_doc.rounding_adjustment,
        }
        report["test_gl_entries"] = payment_utils.dump_gl_entries(test_invoice_name)
        report["test_payment_ledger_entries"] = payment_utils.dump_payment_ledger_entries(test_invoice_name)

        client_row = _get_client_row(test_doc.get("custom_client")) if test_doc.get("custom_client") else None
        paid_to = _resolve_paid_to_account(test_doc, client_row)

        if not paid_to:
            report["success"] = False
            report["error"] = "No valid Bank Account ledger account found to run the payment leg of the test."
        else:
            outstanding_amount = payment_utils.get_outstanding_amount_for_payment(
                test_doc.outstanding_amount, test_doc.grand_total, test_invoice_name
            )

            payment_entry = payment_utils.build_and_submit_payment_entry(
                invoice_name=test_invoice_name,
                paid_to_account=paid_to,
                payment_date=nowdate(),
                remarks="Dashboard invoice/payment rounding self-test",
                final_amount=outstanding_amount,
            )
            test_payment_name = payment_entry.name

            report["success"] = True
            report["payment_entry"] = test_payment_name
            report["payment_amount"] = payment_entry.paid_amount

    except Exception:
        report["success"] = False
        report["traceback"] = frappe.get_traceback()

    finally:
        if test_payment_name and frappe.db.exists("Payment Entry", test_payment_name):
            try:
                pe = frappe.get_doc("Payment Entry", test_payment_name)
                if pe.docstatus == 1:
                    pe.cancel()
                pe.delete()
            except Exception:
                report["cleanup_error_payment"] = frappe.get_traceback()

        if test_invoice_name and frappe.db.exists("Sales Invoice", test_invoice_name):
            try:
                inv = frappe.get_doc("Sales Invoice", test_invoice_name)
                if inv.docstatus == 1:
                    inv.cancel()
                inv.delete()
            except Exception:
                report["cleanup_error_invoice"] = frappe.get_traceback()

        frappe.db.commit()

    return report


# =========================================================
# COUNTS
# =========================================================

def _count_doctype(doctype):
    if not _has_doctype(doctype):
        return 0

    return frappe.db.count(doctype)


def _get_linked_session_worker_count_for_coach(context):
    rows = _get_client_rows_for_coach(context, primary_only=False)

    workers = {
        row.get("session_worker")
        for row in rows
        if row.get("session_worker")
    }

    return len(workers)


# =========================================================
# PUBLIC API
# =========================================================

@frappe.whitelist()
def get_dashboard_summary(dashboard_type=None, view_as=None, viewer=None):
    _require_logged_in_user()

    dashboard_type = _normalise_dashboard_type(dashboard_type)

    view_as = _coalesce_str("view_as", view_as)
    viewer = _coalesce_str("viewer", viewer)

    context = _get_context_for_dashboard(dashboard_type)

    if dashboard_type == COACH_DASHBOARD and view_as:
        view_mode = get_coach_view_mode(
            scope=viewer,
            coach_name=view_as,
        )

        if not view_mode.get("is_view_mode"):
            frappe.throw(_("You do not have permission to view this coach."), frappe.PermissionError)

        context["coach_name"] = view_mode.get("view_coach_name")
        context["coach_label"] = view_mode.get("view_coach_display_name")
        context["is_dashboard_admin"] = 0
        context["is_view_mode"] = 1
        context["view_scope"] = viewer
        context["view_as_user"] = frappe.db.get_value(
            "Coach",
            view_mode.get("view_coach_name"),
            "user",
        ) or frappe.db.get_value(
            "Coach",
            view_mode.get("view_coach_name"),
            "coach_email",
        ) or ""

    if dashboard_type == SESSION_WORKER_DASHBOARD and view_as:
        view_mode = get_session_worker_view_mode(
            scope=viewer,
            worker_name=view_as,
        )

        if not view_mode.get("is_view_mode"):
            frappe.throw(_("You do not have permission to view this session worker."), frappe.PermissionError)

        context["session_worker_name"] = view_mode.get("view_worker_name")
        context["session_worker_label"] = view_mode.get("view_worker_display_name")
        context["is_dashboard_admin"] = 0
        context["is_view_mode"] = 1
        context["view_scope"] = viewer

    current_month_start, current_month_end = _get_current_month_range()
    previous_month_start, previous_month_end = _get_previous_month_range()

    if dashboard_type == SESSION_WORKER_DASHBOARD:
        invoice_frequency = "Monthly"
        invoice_cycle_start_date = None

        worker_name = context.get("session_worker_name")

        if worker_name and frappe.db.exists("Session Worker", worker_name):
            worker_doc = frappe.get_doc("Session Worker", worker_name)
            meta = frappe.get_meta(worker_doc.doctype)

            if meta.has_field("invoice_frequency"):
                invoice_frequency = (worker_doc.get("invoice_frequency") or "Monthly").strip()

            if meta.has_field("invoice_cycle_start_date"):
                invoice_cycle_start_date = worker_doc.get("invoice_cycle_start_date")

        period = _get_period_ranges(invoice_frequency, invoice_cycle_start_date)

        return {
            "dashboard_type": dashboard_type,
            "session_worker_name": context.get("session_worker_label") or context.get("user_label"),
            "session_worker_docname": worker_name or "",
            "invoice_frequency": invoice_frequency,
            "previous_label": period["previous_label"],
            "current_label": period["current_label"],

            "one_to_one_previous": _count_billing_type(
                context, "One to One", period["previous_start"], period["previous_end"]
            ),
            "one_to_one_current": _count_billing_type(
                context, "One to One", period["current_start"], period["current_end"]
            ),

            "group_previous": _count_billing_type(
                context, "Group", period["previous_start"], period["previous_end"]
            ),
            "group_current": _count_billing_type(
                context, "Group", period["current_start"], period["current_end"]
            ),

            "workshop_previous": _count_billing_type(
                context, "Workshop", period["previous_start"], period["previous_end"]
            ),
            "workshop_current": _count_billing_type(
                context, "Workshop", period["current_start"], period["current_end"]
            ),

            "travel_miles_previous": _sum_travel_miles(
                context, period["previous_start"], period["previous_end"]
            ),
            "travel_miles_current": _sum_travel_miles(
                context, period["current_start"], period["current_end"]
            ),

            "upcoming_appointments": _get_upcoming_appointments(dashboard_type, context, limit=8),
        }

    client_rows = _get_dashboard_client_rows(dashboard_type, context, primary_only_for_coach=False)

    revenue_current = _get_invoice_revenue_breakdown(
        dashboard_type, context, current_month_start, current_month_end
    )
    revenue_previous = _get_invoice_revenue_breakdown(
        dashboard_type, context, previous_month_start, previous_month_end
    )

    fees_current = _compute_fees(revenue_current, dashboard_type)
    fees_previous = _compute_fees(revenue_previous, dashboard_type)

    response = {
        "dashboard_type": dashboard_type,
        "current_label": _get_month_label(current_month_start),
        "previous_label": _get_month_label(previous_month_start),

        # Raw period boundaries (the labels above are just "This Month" /
        # "Last Month") - the franchisor dashboard's revenue drill-down
        # links need these to build the matching Invoices list filter.
        "current_month_start": str(current_month_start),
        "current_month_end": str(current_month_end),
        "previous_month_start": str(previous_month_start),
        "previous_month_end": str(previous_month_end),

        "total_clients": len(client_rows),
        "new_clients_current_month": _count_clients_added(client_rows, current_month_start, current_month_end),
        "new_clients_previous_month": _count_clients_added(client_rows, previous_month_start, previous_month_end),

        "upcoming_appointments": _get_upcoming_appointments(dashboard_type, context, limit=8),
        "upcoming_birthdays": _get_upcoming_birthdays(client_rows, days_ahead=14),

        "revenue_total_current": revenue_current["total"],
        "revenue_total_previous": revenue_previous["total"],
        "revenue_client_current": revenue_current["client_total"],
        "revenue_client_previous": revenue_previous["client_total"],
        "revenue_travel_current": revenue_current["travel_total"],
        "revenue_travel_previous": revenue_previous["travel_total"],
        "revenue_interbusiness_current": revenue_current["interbusiness_total"],
        "revenue_interbusiness_previous": revenue_previous["interbusiness_total"],
        "revenue_kids_teens_uni_current": revenue_current["kids_teens_uni_total"],
        "revenue_kids_teens_uni_previous": revenue_previous["kids_teens_uni_total"],
        "revenue_schools_current": revenue_current["schools_total"],
        "revenue_schools_previous": revenue_previous["schools_total"],
        "revenue_people_current": revenue_current["people_total"],
        "revenue_people_previous": revenue_previous["people_total"],

        "gross_revenue_current": fees_current["gross_revenue"],
        "gross_revenue_previous": fees_previous["gross_revenue"],
        "marketing_fee_current": fees_current["marketing_fee"],
        "marketing_fee_previous": fees_previous["marketing_fee"],
        "franchise_fee_current": fees_current["franchise_fee"],
        "franchise_fee_previous": fees_previous["franchise_fee"],
        "franchise_fee_rate_current": fees_current["franchise_fee_rate"],
        "franchise_fee_rate_previous": fees_previous["franchise_fee_rate"],

        "year_to_date_income": _sum_invoice_total_ytd(
            dashboard_type,
            context,
        ),

        "outstanding_invoices": _get_outstanding_invoices(dashboard_type, context, limit=8),
        "outstanding_internal_invoices": _get_outstanding_internal_invoices(
            dashboard_type, context, limit=5 if dashboard_type == COACH_DASHBOARD else 50
        ),

        "clients_url": {
            COACH_DASHBOARD: "/coach_db/clients",
            FRANCHISOR_DASHBOARD: "/franchisor_db/clients",
        }.get(dashboard_type, "/session_worker_db/clients"),

        "calendar_url": {
            COACH_DASHBOARD: "/coach_db/calendar",
            FRANCHISOR_DASHBOARD: "/franchisor_db/calendar",
        }.get(dashboard_type, "/session_worker_db/calendar"),

        "invoices_url": {
            COACH_DASHBOARD: "/coach_db/invoices",
            FRANCHISOR_DASHBOARD: "/franchisor_db/invoices",
        }.get(dashboard_type, "/coach_db/invoices"),

        "session_workers_url": {
            COACH_DASHBOARD: "/coach_db/session_workers",
            FRANCHISOR_DASHBOARD: "/franchisor_db/session_workers",
        }.get(dashboard_type, ""),

        "coaches_url": {
            FRANCHISOR_DASHBOARD: "/franchisor_db/coaches",
        }.get(dashboard_type, ""),
    }

    if dashboard_type == COACH_DASHBOARD:
        response["total_session_workers"] = _get_linked_session_worker_count_for_coach(context)
        response["total_coaches"] = 0

    if dashboard_type == FRANCHISOR_DASHBOARD:
        response["total_session_workers"] = _count_doctype("Session Worker")
        response["total_coaches"] = _count_doctype("Coach")

    return response
