import frappe
from frappe import _
from frappe.utils import today, getdate, get_datetime, add_to_date, flt, nowdate, get_fullname
from dashboard.api.shared.coach_view_mode import get_coach_view_mode
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

    if dashboard_type == COACH_DASHBOARD:
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
    ]

    fields = []

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


def _get_client_rows_for_coach(context, primary_only=False):
    if not _has_doctype("Client"):
        return []

    if context.get("is_dashboard_admin"):
        return frappe.get_all(
            "Client",
            fields=_get_client_fields(),
            order_by="date_added desc",
            limit_page_length=10000,
            ignore_permissions=True,
        )

    coach_name = context.get("coach_name")

    if not coach_name:
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

    if dashboard_type == COACH_DASHBOARD:
        return _get_client_rows_for_coach(context, primary_only=primary_only_for_coach)

    if dashboard_type == FRANCHISOR_DASHBOARD:
        return _get_client_rows_for_franchisor()

    return []


def _count_clients_added(rows, start_date, end_date):
    count = 0

    for row in rows:
        date_added = row.get("date_added")
        if not date_added:
            continue

        date_added = getdate(date_added)

        if getdate(start_date) <= date_added <= getdate(end_date):
            count += 1

    return count


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
        # Dashboard appointments must only be this franchisor user's own appointments.
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
        rows = _get_client_rows_for_franchisor()
        return [row.name for row in rows if row.name]

    return []


def _get_invoice_filters(dashboard_type, context, start_date=None, end_date=None, outstanding_only=False):
    client_names = _get_invoice_client_names_for_dashboard(dashboard_type, context)

    if not client_names:
        return {"name": ["in", []]}

    filters = {
        "custom_client": ["in", client_names],
        "docstatus": ["!=", 2],
    }

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


def _sum_invoice_travel_total(dashboard_type, context, start_date, end_date):
    filters = _get_invoice_filters(
        dashboard_type=dashboard_type,
        context=context,
        start_date=start_date,
        end_date=end_date,
        outstanding_only=False,
    )

    invoice_names = frappe.get_all(
        "Sales Invoice",
        filters=filters,
        pluck="name",
        limit_page_length=10000,
        ignore_permissions=True,
    )

    if not invoice_names:
        return 0.0

    rows = frappe.get_all(
        "Sales Invoice Item",
        filters={"parent": ["in", invoice_names], "item_code": TRAVEL_ITEM_CODE},
        fields=["amount"],
        limit_page_length=100000,
        ignore_permissions=True,
    )

    total = 0.0

    for row in rows:
        total += flt(row.get("amount") or 0)

    return total


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

        invoices.append({
            "name": row.get("name"),
            "client": row.get("custom_client"),
            "client_name": client_name,
            "customer": row.get("customer"),
            "posting_date": str(row.get("posting_date") or ""),
            "due_date": str(row.get("due_date") or ""),
            "status": row.get("status") or "",
            "grand_total": flt(row.get("grand_total") or row.get("rounded_total") or 0),
            "outstanding_amount": flt(row.get("outstanding_amount") or 0),
            "currency": row.get("currency") or "GBP",
            "invoice_url": {
                COACH_DASHBOARD: "/coach_db/invoices",
                FRANCHISOR_DASHBOARD: "/franchisor_db/invoices",
            }.get(dashboard_type, "/coach_db/invoices"),
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

    return (client_row.get("primary_coach") or "").strip() == (context.get("coach_name") or "").strip()


def _get_paid_to_account_from_client(client_row):
    if not client_row:
        return ""

    bank_account = client_row.get("banking")

    if not bank_account:
        return ""

    if not frappe.db.exists("Bank Account", bank_account):
        return ""

    bank_meta = frappe.get_meta("Bank Account")

    for fieldname in ["account", "account_name"]:
        if bank_meta.has_field(fieldname):
            value = frappe.db.get_value("Bank Account", bank_account, fieldname)
            if value and frappe.db.exists("Account", value):
                return value

    return ""


@frappe.whitelist()
def mark_invoice_paid(invoice=None, payment_date=None, dashboard_type=None):
    user = _require_logged_in_user()
    dashboard_type = _normalise_dashboard_type(dashboard_type)
    context = _get_context_for_dashboard(dashboard_type)

    invoice = _coalesce_str("invoice", invoice)
    payment_date = _coalesce_str("payment_date", payment_date) or today()

    if not invoice:
        frappe.throw(_("Please select an invoice."))

    if not _user_can_access_invoice(invoice, dashboard_type, context):
        frappe.throw(_("You do not have permission to mark this invoice as paid."), frappe.PermissionError)

    invoice_doc = frappe.get_doc("Sales Invoice", invoice)

    if invoice_doc.docstatus != 1:
        frappe.throw(_("Only submitted Sales Invoices can be marked as paid."))

    outstanding_amount = flt(invoice_doc.outstanding_amount or 0)

    if outstanding_amount <= 0:
        return {
            "ok": True,
            "message": "Invoice is already paid.",
            "invoice": invoice,
        }

    client_row = _get_client_row(invoice_doc.get("custom_client"))

    paid_to = _get_paid_to_account_from_client(client_row)

    if not paid_to:
        frappe.throw(_("No valid Bank Account ledger account was found from the Client banking field."))

    company = invoice_doc.company or (client_row.get("company") if client_row else "")

    if not company:
        frappe.throw(_("No company found for this invoice."))

    if not invoice_doc.customer:
        frappe.throw(_("No customer found for this invoice."))

    payment_entry = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Receive",
        "posting_date": payment_date,
        "company": company,
        "party_type": "Customer",
        "party": invoice_doc.customer,
        "party_name": invoice_doc.customer_name,
        "paid_from": invoice_doc.debit_to,
        "paid_to": paid_to,
        "paid_amount": outstanding_amount,
        "received_amount": outstanding_amount,
        "reference_no": f"Dashboard payment - {invoice}",
        "reference_date": payment_date,
        "remarks": f"Payment marked as paid from dashboard by {user}",
        "references": [
            {
                "reference_doctype": "Sales Invoice",
                "reference_name": invoice,
                "total_amount": flt(invoice_doc.grand_total or invoice_doc.rounded_total or 0),
                "outstanding_amount": outstanding_amount,
                "allocated_amount": outstanding_amount,
            }
        ],
    })

    payment_entry.insert(ignore_permissions=True)
    payment_entry.submit()

    return {
        "ok": True,
        "message": "Payment Entry created.",
        "invoice": invoice,
        "payment_entry": payment_entry.name,
    }


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

    monthly_travel_total_current = _sum_invoice_travel_total(
        dashboard_type, context, current_month_start, current_month_end
    )
    monthly_travel_total_previous = _sum_invoice_travel_total(
        dashboard_type, context, previous_month_start, previous_month_end
    )
    monthly_invoice_total_current = _sum_invoice_total(
        dashboard_type, context, current_month_start, current_month_end
    )
    monthly_invoice_total_previous = _sum_invoice_total(
        dashboard_type, context, previous_month_start, previous_month_end
    )

    # Coach dashboard shows travel as its own pair of blocks rather than
    # folded into the invoice totals, so it needs pulling back out here.
    # Franchisor keeps the combined total as before - not asked to change.
    if dashboard_type == COACH_DASHBOARD:
        monthly_invoice_total_current -= monthly_travel_total_current
        monthly_invoice_total_previous -= monthly_travel_total_previous

    response = {
        "dashboard_type": dashboard_type,
        "current_label": _get_month_label(current_month_start),
        "previous_label": _get_month_label(previous_month_start),

        "total_clients": len(client_rows),
        "new_clients_current_month": _count_clients_added(client_rows, current_month_start, current_month_end),
        "new_clients_previous_month": _count_clients_added(client_rows, previous_month_start, previous_month_end),

        "upcoming_appointments": _get_upcoming_appointments(dashboard_type, context, limit=8),

        "monthly_invoice_total_current": monthly_invoice_total_current,
        "monthly_invoice_total_previous": monthly_invoice_total_previous,
        "monthly_travel_total_current": monthly_travel_total_current,
        "monthly_travel_total_previous": monthly_travel_total_previous,
        "year_to_date_income": _sum_invoice_total_ytd(
            dashboard_type,
            context,
        ),

        "outstanding_invoices": _get_outstanding_invoices(dashboard_type, context, limit=8),

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
