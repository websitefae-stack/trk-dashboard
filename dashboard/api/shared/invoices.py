import frappe
from frappe import _


FRANCHISOR_USERS = [
    "ashley@theresilientkid.co.uk",
    "hq@theresilientkid.co.uk",
    "office@theresilientpeople.uk",
]

COACH_DASHBOARD = "coach"
FRANCHISOR_DASHBOARD = "franchisor"


def _require_logged_in_user():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    return frappe.session.user


def _is_franchisor_user():
    return (frappe.session.user or "").strip().lower() in {
        email.lower() for email in FRANCHISOR_USERS
    }


def _normalise_dashboard_type(dashboard_type=None):
    dashboard_type = (dashboard_type or "").strip().lower()

    if dashboard_type in [COACH_DASHBOARD, FRANCHISOR_DASHBOARD]:
        return dashboard_type

    try:
        referrer = frappe.request.headers.get("Referer") or ""
        if "/franchisor_db" in referrer:
            return FRANCHISOR_DASHBOARD
        if "/coach_db" in referrer:
            return COACH_DASHBOARD
    except Exception:
        pass

    return COACH_DASHBOARD


def _get_current_coach():
    user = _require_logged_in_user()

    if not frappe.db.exists("DocType", "Coach"):
        return None

    meta = frappe.get_meta("Coach")
    fields = ["name"]

    for fieldname in ["coach_name", "full_name", "company", "user", "user_id", "email", "coach_email"]:
        if meta.has_field(fieldname) and fieldname not in fields:
            fields.append(fieldname)

    login_fields = ["user", "user_id", "email", "coach_email"]

    for fieldname in login_fields:
        if meta.has_field(fieldname):
            row = frappe.db.get_value("Coach", {fieldname: user}, fields, as_dict=True)
            if row:
                return row

    return None


def _coach_label(coach):
    if not coach:
        return ""

    first = (
        coach.get("coach_name")
        or coach.get("name1")
        or coach.get("first_name")
        or ""
    )

    last = coach.get("last_name") or ""

    full = " ".join([part for part in [first, last] if part]).strip()

    return full or coach.get("full_name") or coach.get("name") or ""


def _get_coach_options():
    if not frappe.db.exists("DocType", "Coach"):
        return []

    meta = frappe.get_meta("Coach")
    fields = ["name"]

    for fieldname in ["coach_name", "name1", "first_name", "last_name", "full_name"]:
        if meta.has_field(fieldname):
            fields.append(fieldname)

    if meta.has_field("coach_name"):
        order_by = "coach_name asc, name asc"
    elif meta.has_field("name1"):
        order_by = "name1 asc, last_name asc, name asc" if meta.has_field("last_name") else "name1 asc, name asc"
    elif meta.has_field("first_name"):
        order_by = "first_name asc, last_name asc, name asc" if meta.has_field("last_name") else "first_name asc, name asc"
    elif meta.has_field("full_name"):
        order_by = "full_name asc, name asc"
    else:
        order_by = "name asc"

    rows = frappe.get_all(
        "Coach",
        fields=fields,
        order_by=order_by,
        limit_page_length=1000,
        ignore_permissions=True,
    )

    return [
        {
            "value": row.get("name"),
            "label": _coach_label(row),
        }
        for row in rows
    ]


def _get_client_fields():
    meta = frappe.get_meta("Client")
    fields = ["name"]

    for fieldname in [
        "full_name",
        "name1",
        "last_name",
        "preferred_name",
        "primary_coach",
        "attending_coach",
        "company",
        "banking",
    ]:
        if meta.has_field(fieldname):
            fields.append(fieldname)

    return fields


def _client_display_name(row):
    if not row:
        return ""

    return (
        row.get("full_name")
        or row.get("preferred_name")
        or " ".join([part for part in [row.get("name1"), row.get("last_name")] if part]).strip()
        or row.get("name")
        or ""
    )


def _get_clients_for_invoice_scope(current_coach, selected_coach=None, dashboard_type=None):
    if not current_coach:
        return []

    if not frappe.db.exists("DocType", "Client"):
        return []

    current_coach_name = current_coach.get("name")
    selected_coach = (selected_coach or "").strip()

    # Default list:
    # show invoices for clients where logged-in coach/franchisor is the PRIMARY coach.
    if not selected_coach:
        filters = {"primary_coach": current_coach_name}

    # Franchisor selected coach:
    # franchisor can view invoices for all clients where selected coach is primary.
    elif dashboard_type == FRANCHISOR_DASHBOARD and _is_franchisor_user():
        filters = {"primary_coach": selected_coach}

    # Coach selected another coach:
    # can only view selected coach's primary clients where logged-in coach is attending coach.
    else:
        filters = {
            "primary_coach": selected_coach,
            "attending_coach": current_coach_name,
        }

    return frappe.get_all(
        "Client",
        filters=filters,
        fields=_get_client_fields(),
        order_by="full_name asc, name1 asc, last_name asc",
        limit_page_length=5000,
        ignore_permissions=True,
    )


def _get_invoice_fields():
    fields = [
        "name",
        "posting_date",
        "due_date",
        "custom_client",
        "customer",
        "customer_name",
        "status",
        "grand_total",
        "rounded_total",
        "outstanding_amount",
        "paid_amount",
        "currency",
        "company",
        "docstatus",
    ]

    meta = frappe.get_meta("Sales Invoice")

    for fieldname in ["custom_created_by_coach", "custom_income_owner_coach"]:
        if meta.has_field(fieldname):
            fields.append(fieldname)

    return fields


def _invoice_status_class(status):
    if status == "Paid":
        return "dashboard-status-active"

    if status in ["Partly Paid", "Draft"]:
        return "dashboard-status-onhold"

    return "dashboard-status-archived"


def _normalise_invoice_row(row, client_map, dashboard_type):
    client_name = row.get("custom_client")
    client_row = client_map.get(client_name) if client_name else None

    base_url = "/franchisor_db/invoice_details" if dashboard_type == FRANCHISOR_DASHBOARD else "/coach_db/invoice_details"

    return {
        "name": row.get("name"),
        "posting_date": str(row.get("posting_date") or ""),
        "due_date": str(row.get("due_date") or ""),
        "custom_client": client_name or "",
        "client_name": _client_display_name(client_row) if client_row else row.get("customer_name") or row.get("customer") or "—",
        "customer": row.get("customer") or "",
        "customer_name": row.get("customer_name") or "",
        "status": row.get("status") or "",
        "status_class": _invoice_status_class(row.get("status") or ""),
        "grand_total": row.get("grand_total") or row.get("rounded_total") or 0,
        "outstanding_amount": row.get("outstanding_amount") or 0,
        "paid_amount": row.get("paid_amount") or 0,
        "currency": row.get("currency") or "GBP",
        "company": row.get("company") or "",
        "docstatus": row.get("docstatus") or 0,
        "details_url": f"{base_url}?name={row.get('name')}",
    }


def _get_invoices_for_clients(client_rows, dashboard_type):
    client_names = [row.get("name") for row in client_rows if row.get("name")]

    if not client_names:
        return []

    invoice_rows = frappe.get_all(
        "Sales Invoice",
        filters={
            "custom_client": ["in", client_names],
            "docstatus": ["!=", 2],
        },
        fields=_get_invoice_fields(),
        order_by="posting_date desc, modified desc",
        limit_page_length=1000,
        ignore_permissions=True,
    )

    client_map = {row.get("name"): row for row in client_rows if row.get("name")}

    return [
        _normalise_invoice_row(row, client_map, dashboard_type)
        for row in invoice_rows
    ]


@frappe.whitelist()
def get_invoice_page_data(dashboard_type=None, selected_coach=None):
    _require_logged_in_user()

    dashboard_type = _normalise_dashboard_type(dashboard_type)

    if dashboard_type == FRANCHISOR_DASHBOARD and not _is_franchisor_user():
        frappe.throw(_("You do not have permission to access the franchisor invoices."), frappe.PermissionError)

    if dashboard_type not in [COACH_DASHBOARD, FRANCHISOR_DASHBOARD]:
        frappe.throw(_("Invoices are only available for coaches and franchisors."), frappe.PermissionError)

    current_coach = _get_current_coach()

    if not current_coach:
        frappe.throw(_("Your user is not linked to a Coach record."), frappe.PermissionError)

    selected_coach = (selected_coach or "").strip()
    current_coach_name = (current_coach.get("name") or "").strip()

    # IMPORTANT:
    # The current user's own invoices are the default view.
    # If the dropdown sends the current coach name, treat it the same as no selected coach.
    if selected_coach == current_coach_name:
        selected_coach = ""

    client_rows = _get_clients_for_invoice_scope(
        current_coach=current_coach,
        selected_coach=selected_coach,
        dashboard_type=dashboard_type,
    )

    invoices = _get_invoices_for_clients(client_rows, dashboard_type)

    return {
        "dashboard_type": dashboard_type,
        "current_coach": current_coach_name,
        "current_coach_label": _coach_label(current_coach),
        "current_company": current_coach.get("company") or "",
        "selected_coach": selected_coach,
        "is_franchisor": 1 if _is_franchisor_user() else 0,
        "coach_options": _get_coach_options(),
        "invoices": invoices,
    }
