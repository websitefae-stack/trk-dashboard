import json
import frappe
from frappe import _
from frappe.utils import nowdate, flt

from dashboard.api.shared.pagination import get_page_args, make_pagination
from dashboard.api.shared.email_templates import render_email, plain_text_to_email_html, parse_email_list, INVOICE_EMAIL_TEMPLATE
from dashboard.api.shared import payment_utils


FRANCHISOR_USERS = [
    "ashley@theresilientkid.co.uk",
    "hq@theresilientkid.co.uk",
    "office@theresilienthub.co.uk",
]

COACH_DASHBOARD = "coach"
FRANCHISOR_DASHBOARD = "franchisor"

TRAVEL_ITEM_CODE = "TRA002"
TRAVEL_RATE_PER_MILE = 0.55
FREE_MILES_ONE_WAY = 10
SINGLE_SESSION_ITEMS = ["COA001", "FAM001", "INI001", "PAR001"]

PARENT_CHECKIN_ITEM_CODE = "PAR001"

# Client types that receive Parent Check-In sessions as part of a package.
# Adult, School, and Company clients do not receive Parent Check-Ins.
_CLIENT_TYPES_WITH_PARENT_CHECKINS = {"Kid", "Teen", "Uni Student"}


# =====================================================
# BASIC HELPERS
# =====================================================

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


def _has_doctype(doctype):
    return frappe.db.exists("DocType", doctype)


def _client_includes_parent_checkins(client_name):
    """Single source of truth: Kid, Teen, and Uni Student clients receive Parent Check-In sessions.
    Adult, School, and Company clients do not.
    Returns True (inclusive) when the client is not found, to avoid silently dropping sessions.
    """
    if not client_name or not frappe.db.exists("Client", client_name):
        return True
    client_type = frappe.db.get_value("Client", client_name, "client_type") or ""
    return client_type in _CLIENT_TYPES_WITH_PARENT_CHECKINS


def _has_field(doctype, fieldname):
    if not _has_doctype(doctype):
        return False

    return frappe.get_meta(doctype).has_field(fieldname)


def _parse_payload(value):
    if isinstance(value, str):
        return json.loads(value) if value else {}

    return value or {}


def _to_float(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


# =====================================================
# COACH / CLIENT / CUSTOMER HELPERS
# =====================================================

def _get_current_coach():
    user = _require_logged_in_user()

    if not _has_doctype("Coach"):
        return None

    meta = frappe.get_meta("Coach")
    fields = ["name"]

    for fieldname in [
        "coach_name",
        "name1",
        "first_name",
        "last_name",
        "full_name",
        "company",
        "user",
        "user_id",
        "email",
        "coach_email",
    ]:
        if meta.has_field(fieldname) and fieldname not in fields:
            fields.append(fieldname)

    login_fields = ["user", "user_id", "email", "coach_email"]

    for fieldname in login_fields:
        if meta.has_field(fieldname):
            row = frappe.db.get_value("Coach", {fieldname: user}, fields, as_dict=True)
            if row:
                return row

    return None


def _get_current_coach_name():
    coach = _get_current_coach()
    return coach.get("name") if coach else ""


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


def _coach_label_from_name(coach_name):
    if not coach_name:
        return ""

    if not frappe.db.exists("Coach", coach_name):
        return coach_name

    meta = frappe.get_meta("Coach")
    fields = ["name"]

    for fieldname in ["coach_name", "name1", "first_name", "last_name", "full_name"]:
        if meta.has_field(fieldname):
            fields.append(fieldname)

    row = frappe.db.get_value("Coach", coach_name, fields, as_dict=True)
    return _coach_label(row) if row else coach_name


def _get_coach_options():
    if not _has_doctype("Coach"):
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


BANK_OVERRIDE_CLIENT_TYPES = ("Franchise", "School")


def _get_bank_account_options():
    """
    Bank Account records tied to a Coach, offered as override choices when
    invoicing a Franchise/School client - e.g. Emily invoicing on SJ's
    behalf needs to pick SJ's own bank account, not whichever one that
    client defaults to.
    """
    if not _has_doctype("Coach"):
        return []

    meta = frappe.get_meta("Coach")
    if not meta.has_field("bank_account"):
        return []

    fields = ["name", "bank_account"]
    for fieldname in ["coach_name", "name1", "first_name", "last_name", "full_name"]:
        if meta.has_field(fieldname):
            fields.append(fieldname)

    rows = frappe.get_all(
        "Coach",
        filters={"bank_account": ["is", "set"]},
        fields=fields,
        order_by="name asc",
        limit_page_length=1000,
        ignore_permissions=True,
    )

    return [
        {
            "value": row.get("bank_account"),
            "label": _coach_label(row),
            "display_text": _bank_display_text(row.get("bank_account")),
        }
        for row in rows
        if row.get("bank_account")
    ]


def _get_bank_account_owner_coach(bank_account_name):
    """
    Reverse lookup of _get_bank_account_options() - given a bank account that
    was picked as an override, find which Coach it belongs to, so the invoice
    (and its income) can be attributed to that coach rather than the client's
    own primary coach.
    """
    if not bank_account_name or not _has_doctype("Coach"):
        return ""

    if not frappe.get_meta("Coach").has_field("bank_account"):
        return ""

    return frappe.db.get_value("Coach", {"bank_account": bank_account_name}, "name") or ""


def _get_coach_company(coach_name):
    if not coach_name or not _has_doctype("Coach"):
        return ""

    meta = frappe.get_meta("Coach")

    for fieldname in ["company", "coach_company"]:
        if meta.has_field(fieldname):
            value = frappe.db.get_value("Coach", coach_name, fieldname)
            if value:
                return value

    return ""


def _ensure_default_bank_account_option(options, default_bank_account):
    """
    _get_bank_account_options() only lists Coach records that have their own
    bank_account filled in on their profile. A client's own default account
    (e.g. HQ's account on a Franchise-type client) may not be linked to any
    Coach that way, which would leave it missing from the dropdown entirely -
    always include it so the default itself is never unselectable.
    """
    if not default_bank_account:
        return options

    if any((opt or {}).get("value") == default_bank_account for opt in options):
        return options

    owner_coach = _get_bank_account_owner_coach(default_bank_account)
    label = _coach_label_from_name(owner_coach) if owner_coach else _bank_display_text(default_bank_account) or default_bank_account

    return options + [{
        "value": default_bank_account,
        "label": label,
        "display_text": _bank_display_text(default_bank_account),
    }]


def _get_client_fields():
    if not _has_doctype("Client"):
        return []

    meta = frappe.get_meta("Client")
    fields = ["name"]

    for fieldname in [
        "full_name",
        "name1",
        "first_name",
        "last_name",
        "preferred_name",
        "primary_coach",
        "attending_coach",
        "session_worker",
        "company",
        "banking",
        "pricelist",
        "billing_contact",
        "travel_charged",
        "travel_miles_one_way",
    ]:
        if meta.has_field(fieldname):
            fields.append(fieldname)

    return fields


def _client_display_from_row(row):
    if not row:
        return ""

    return (
        row.get("full_name")
        or row.get("preferred_name")
        or " ".join([part for part in [row.get("name1") or row.get("first_name"), row.get("last_name")] if part]).strip()
        or row.get("name")
        or ""
    )


def _client_display_name(client_name):
    if not client_name:
        return ""

    if not frappe.db.exists("Client", client_name):
        return client_name

    row = frappe.db.get_value("Client", client_name, _get_client_fields(), as_dict=True)
    return _client_display_from_row(row) if row else client_name


def _customer_display_name(customer_name):
    if not customer_name:
        return ""

    if frappe.db.exists("Customer", customer_name):
        return frappe.db.get_value("Customer", customer_name, "customer_name") or customer_name

    return customer_name


def _customer_email(customer_name):
    if not customer_name or not frappe.db.exists("Customer", customer_name):
        return ""

    customer_email = frappe.db.get_value("Customer", customer_name, "email_id")
    if customer_email:
        return customer_email

    primary_contact = frappe.db.get_value(
        "Customer",
        customer_name,
        "customer_primary_contact",
    )

    if primary_contact and frappe.db.exists("Contact", primary_contact):
        contact_email = frappe.db.get_value("Contact", primary_contact, "email_id")
        if contact_email:
            return contact_email

    linked_contact = frappe.db.get_value(
        "Dynamic Link",
        {
            "parenttype": "Contact",
            "link_doctype": "Customer",
            "link_name": customer_name,
        },
        "parent",
    )

    if linked_contact and frappe.db.exists("Contact", linked_contact):
        contact_email = frappe.db.get_value("Contact", linked_contact, "email_id")
        if contact_email:
            return contact_email

    contact_from_custom_customer = frappe.db.get_value(
        "Contact",
        {"custom_customer": customer_name},
        "email_id",
    )

    return contact_from_custom_customer or ""


def _bank_display_text(bank_account_name):
    if not bank_account_name or not frappe.db.exists("Bank Account", bank_account_name):
        return ""

    bank_meta = frappe.get_meta("Bank Account")
    fields = []

    for fieldname in ["bank", "custom_bank_account_name", "bank_account_no", "branch_code"]:
        if bank_meta.has_field(fieldname):
            fields.append(fieldname)

    if not fields:
        return bank_account_name

    bank = frappe.db.get_value("Bank Account", bank_account_name, fields, as_dict=True) or {}

    lines = [
        f"Bank Name: {bank.get('bank') or ''}",
        f"Account Name: {bank.get('custom_bank_account_name') or ''}",
        f"Account Number: {bank.get('bank_account_no') or ''}",
        f"Branch Code: {bank.get('branch_code') or ''}",
    ]

    return "\n".join([line for line in lines if line.split(": ", 1)[1].strip()])


# =====================================================
# PERMISSION / SCOPE HELPERS
# =====================================================

def _current_user_can_access_client(client_name):
    if not client_name:
        return False

    if _is_franchisor_user():
        return True

    current_coach_name = _get_current_coach_name()

    if not current_coach_name:
        return False

    client = frappe.db.get_value(
        "Client",
        client_name,
        ["primary_coach", "attending_coach", "client_type"],
        as_dict=True,
    )

    if not client:
        return False

    # Franchise-type clients represent coaches themselves (for cross-coach/HQ
    # invoicing) and aren't tied to a specific primary/attending coach, so
    # every coach needs to be able to invoice them regardless of assignment -
    # matching the same carve-out in get_allowed_client_or_filters().
    if client.get("client_type") == "Franchise":
        return True

    return (
        client.get("primary_coach") == current_coach_name
        or client.get("attending_coach") == current_coach_name
    )


def _current_user_can_access_invoice(invoice_name):
    if not invoice_name or not frappe.db.exists("Sales Invoice", invoice_name):
        return False

    invoice = frappe.db.get_value(
        "Sales Invoice",
        invoice_name,
        ["custom_client"],
        as_dict=True,
    )

    if not invoice:
        return False

    return _current_user_can_access_client(invoice.get("custom_client"))


def _get_allowed_clients_for_user():
    if _is_franchisor_user():
        return None

    current_coach_name = _get_current_coach_name()

    if not current_coach_name:
        return []

    filters = []

    if frappe.db.has_column("Client", "primary_coach"):
        filters.append(["primary_coach", "=", current_coach_name])

    if frappe.db.has_column("Client", "attending_coach"):
        filters.append(["attending_coach", "=", current_coach_name])

    if not filters:
        return []

    client_names = set()

    for condition in filters:
        rows = frappe.get_all(
            "Client",
            filters=[condition],
            pluck="name",
            limit_page_length=5000,
            ignore_permissions=True,
        )

        for name in rows:
            client_names.add(name)

    if frappe.db.has_column("Client", "client_type"):
        # Franchise-type clients represent coaches themselves and need to be
        # invoiceable by any coach, regardless of primary/attending coach -
        # see _current_user_can_access_client().
        for name in frappe.get_all(
            "Client",
            filters={"client_type": "Franchise"},
            pluck="name",
            limit_page_length=5000,
            ignore_permissions=True,
        ):
            client_names.add(name)

    return sorted(client_names)


def _get_clients_for_invoice_scope(current_coach, selected_coach=None, dashboard_type=None):
    if not current_coach:
        return []

    if not _has_doctype("Client"):
        return []

    current_coach_name = current_coach.get("name")
    selected_coach = (selected_coach or "").strip()

    if not selected_coach:
        filters = {"primary_coach": current_coach_name}

    elif dashboard_type == FRANCHISOR_DASHBOARD and _is_franchisor_user():
        filters = {"primary_coach": selected_coach}

    else:
        filters = {
            "primary_coach": selected_coach,
            "attending_coach": current_coach_name,
        }

    meta = frappe.get_meta("Client")

    if meta.has_field("full_name"):
        order_by = "full_name asc, name asc"
    elif meta.has_field("name1"):
        order_by = "name1 asc, last_name asc, name asc" if meta.has_field("last_name") else "name1 asc, name asc"
    else:
        order_by = "name asc"

    return frappe.get_all(
        "Client",
        filters=filters,
        fields=_get_client_fields(),
        order_by=order_by,
        limit_page_length=5000,
        ignore_permissions=True,
    )


# =====================================================
# INVOICE LIST HELPERS
# =====================================================

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

    posting_date = row.get("posting_date")

    return {
        "name": row.get("name"),
        "posting_date": str(posting_date or ""),
        "posting_date_display": frappe.utils.formatdate(posting_date, "dd-MM-yyyy") if posting_date else "—",
        "due_date": str(row.get("due_date") or ""),
        "custom_client": client_name or "",
        "client_name": (
            _client_display_from_row(client_row) if client_row
            else _client_display_name(client_name) if client_name
            else row.get("customer_name") or row.get("customer") or "—"
        ),
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


def _amount_search_text(amount):
    """Lets the invoice list's search box match on the total, e.g. "150" finds a £150.00 invoice."""
    try:
        value = float(amount or 0)
    except (TypeError, ValueError):
        return ""
    return f"{value:.2f} {value:g}"


def _get_invoices_for_clients(client_rows, dashboard_type, owner_coach_name=None):
    page_args = get_page_args()
    search = page_args["search"].lower()

    client_names = [row.get("name") for row in client_rows if row.get("name")]

    or_conditions = []
    if client_names:
        or_conditions.append(["custom_client", "in", client_names])

    if owner_coach_name and frappe.get_meta("Sales Invoice").has_field("custom_income_owner_coach"):
        # Invoices created with an overridden bank account (e.g. Emily
        # invoicing on SJ's behalf with her own account) are attributed to
        # the overriding coach via custom_income_owner_coach, even though
        # the client itself isn't one of this coach's own clients - they
        # still need to show up in that coach's own invoice list.
        or_conditions.append(["custom_income_owner_coach", "=", owner_coach_name])

    if not or_conditions:
        return {
            "invoices": [],
            "pagination": make_pagination(0, page_args["page"], page_args["page_size"]),
            "search": page_args["search"],
        }

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

    client_map = {row.get("name"): row for row in client_rows if row.get("name")}

    invoice_rows = frappe.get_all(
        "Sales Invoice",
        filters=filters,
        fields=_get_invoice_fields(),
        order_by="posting_date desc, modified desc",
        limit_page_length=0 if search else page_args["page_size"],
        start=0 if search else page_args["start"],
        ignore_permissions=True,
    )

    invoices = [
        _normalise_invoice_row(row, client_map, dashboard_type)
        for row in invoice_rows
    ]

    if search:
        invoices = [
            inv for inv in invoices
            if search in (inv.get("name") or "").lower()
            or search in (inv.get("client_name") or "").lower()
            or search in (inv.get("customer_name") or "").lower()
            or search in (inv.get("customer") or "").lower()
            or search in (inv.get("company") or "").lower()
            or search in _amount_search_text(inv.get("grand_total"))
        ]

        total = len(invoices)
        invoices = invoices[
            page_args["start"]:page_args["start"] + page_args["page_size"]
        ]
    else:
        total_rows = frappe.get_all(
            "Sales Invoice",
            filters=filters,
            pluck="name",
            limit_page_length=0,
            ignore_permissions=True,
        )
        total = len(total_rows)

    return {
        "invoices": invoices,
        "pagination": make_pagination(
            total,
            page_args["page"],
            page_args["page_size"],
        ),
        "search": page_args["search"],
    }


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

    if selected_coach == current_coach_name:
        selected_coach = ""

    client_rows = _get_clients_for_invoice_scope(
        current_coach=current_coach,
        selected_coach=selected_coach,
        dashboard_type=dashboard_type,
    )

    owner_coach_name = ""
    if dashboard_type == COACH_DASHBOARD:
        owner_coach_name = selected_coach or current_coach_name

    invoice_data = _get_invoices_for_clients(client_rows, dashboard_type, owner_coach_name=owner_coach_name)
    invoices = invoice_data.get("invoices", [])

    return {
        "dashboard_type": dashboard_type,
        "current_coach": current_coach_name,
        "current_coach_label": _coach_label(current_coach),
        "current_company": current_coach.get("company") or "",
        "selected_coach": selected_coach,
        "is_franchisor": 1 if _is_franchisor_user() else 0,
        "coach_options": _get_coach_options(),
        "invoices": invoices,
        "pagination": invoice_data.get("pagination", {}),
        "search": invoice_data.get("search", ""),
    }


# =====================================================
# INVOICE DETAILS CONTEXT HELPERS
# =====================================================

def _default_naming_series():
    meta = frappe.get_meta("Sales Invoice")
    df = meta.get_field("naming_series")
    if not df:
        return ""

    options = [row.strip() for row in (df.options or "").split("\n") if row.strip()]
    return options[0] if options else ""


def _item_price_from_price_list(item_code, price_list):
    if not item_code or not price_list:
        return 0

    rows = frappe.get_all(
        "Item Price",
        filters={
            "item_code": item_code,
            "price_list": price_list,
            "selling": 1,
        },
        fields=["price_list_rate"],
        order_by="valid_from desc, modified desc",
        limit_page_length=1,
        ignore_permissions=True,
    )

    return rows[0].get("price_list_rate") if rows else 0


def _get_billable_session_count_for_item(item_code):
    # Parent Check-Ins are delivered online and never incur travel, so they
    # never count toward the travel-billable session total - whether booked
    # as their own invoice line or bundled inside a package alongside other
    # (travel-eligible) sessions.
    if not item_code or item_code == TRAVEL_ITEM_CODE or item_code == PARENT_CHECKIN_ITEM_CODE:
        return 0

    product_bundle_name = frappe.db.get_value(
        "Product Bundle",
        {
            "new_item_code": item_code,
            "disabled": 0,
        },
        "name",
    )

    if product_bundle_name:
        total_sessions = 0
        product_bundle = frappe.get_doc("Product Bundle", product_bundle_name)

        for bundle_item in product_bundle.get("items") or []:
            service_item = bundle_item.get("item_code")
            qty = _to_float(bundle_item.get("qty"))

            if service_item and service_item not in (TRAVEL_ITEM_CODE, PARENT_CHECKIN_ITEM_CODE):
                total_sessions += qty

        return total_sessions

    if item_code in SINGLE_SESSION_ITEMS:
        return 1

    return 0


def _item_defaults(item_code=None, company=None, customer=None, price_list=None):
    item_code = (item_code or "").strip()

    if not item_code:
        return {
            "item_code": "",
            "item_name": "",
            "description": "",
            "rate": 0,
            "uom": "",
            "bundle_session_count": 0,
        }

    item_doc = frappe.get_doc("Item", item_code)
    rate = _item_price_from_price_list(item_code, price_list)

    return {
        "item_code": item_code,
        "item_name": item_doc.item_name or item_code,
        "description": item_doc.description or item_doc.item_name or item_code,
        "rate": rate or 0,
        "uom": item_doc.stock_uom or "",
        "bundle_session_count": _get_billable_session_count_for_item(item_code),
    }


def _get_total_billable_sessions_from_payload(items_payload):
    total_sessions = 0

    for row in items_payload or []:
        item_code = (row.get("item_code") or "").strip()

        if not item_code or item_code == TRAVEL_ITEM_CODE:
            continue

        row_qty = _to_float(row.get("qty")) or 1
        sessions_per_item = _get_billable_session_count_for_item(item_code)
        total_sessions += sessions_per_item * row_qty

    return total_sessions


def _build_travel_row_for_client(client_name, total_sessions):
    if not client_name or not total_sessions:
        return None

    if not frappe.db.exists("Client", client_name):
        return None

    client = frappe.get_doc("Client", client_name)

    travel_charged = int(client.get("travel_charged") or 0)
    rate_per_session = _to_float(client.get("travel_charge_per_session"))

    if not travel_charged or not rate_per_session:
        return None

    description = (
        f"Travel charge for {total_sessions:g} session"
        f"{'' if total_sessions == 1 else 's'} at this client's agreed rate of "
        f"£{rate_per_session:g} per session. (Travel is charged at £{TRAVEL_RATE_PER_MILE:g} "
        f"per mile, with the first {FREE_MILES_ONE_WAY:g} miles each way free.)"
    )

    return {
        "item_code": TRAVEL_ITEM_CODE,
        "description": description,
        "qty": total_sessions,
        "rate": rate_per_session,
    }


def _with_auto_travel_items(client_name, items_payload):
    existing_travel_rows = [
        row for row in (items_payload or [])
        if (row.get("item_code") or "").strip() == TRAVEL_ITEM_CODE
    ]
    other_items = [
        row for row in (items_payload or [])
        if (row.get("item_code") or "").strip() != TRAVEL_ITEM_CODE
    ]

    total_sessions = _get_total_billable_sessions_from_payload(other_items)
    travel_row = _build_travel_row_for_client(client_name, total_sessions)

    if travel_row:
        # Travel is a standing charge for this client - always reflect the
        # current rate/session count rather than whatever was last saved.
        other_items.append(travel_row)
    elif existing_travel_rows:
        # Not a standing charge (box unticked, or no rate set) - any travel
        # line here was added manually, so leave it exactly as submitted
        # instead of silently deleting it.
        other_items.extend(existing_travel_rows)

    return other_items


def _resolve_invoice_context(client_name=None, customer_name=None):
    client_name = (client_name or "").strip()
    customer_name = (customer_name or "").strip()

    context = {
        "client_name": client_name,
        "client_label": _client_display_name(client_name),
        "customer_name": customer_name,
        "customer_label": _customer_display_name(customer_name),
        "company": "",
        "price_list": "",
        "coach_label": "",
        "bank_account": "",
        "client_bank_account": "",
        "bank_display_text": "",
        "allow_bank_override": False,
        "bank_account_options": [],
        "contact_email": _customer_email(customer_name),
        "always_confirm_bank_account": False,
    }

    if client_name and frappe.db.exists("Client", client_name):
        client = frappe.get_doc("Client", client_name)

        allow_bank_override = (client.get("client_type") or "") in BANK_OVERRIDE_CLIENT_TYPES

        context["company"] = client.get("company") or ""
        context["price_list"] = client.get("pricelist") or ""
        context["coach_label"] = _coach_label_from_name(client.get("attending_coach") or client.get("primary_coach") or "")
        context["bank_account"] = client.get("banking") or ""
        context["client_bank_account"] = client.get("banking") or ""
        context["bank_display_text"] = _bank_display_text(client.get("banking") or "")
        context["allow_bank_override"] = allow_bank_override
        context["bank_account_options"] = (
            _ensure_default_bank_account_option(_get_bank_account_options(), context["bank_account"])
            if allow_bank_override else []
        )
        # Franchise-type clients represent another coach or HQ - an
        # interbusiness/cross-coach invoice, where the receiving bank
        # account deserves a confirmation every time, not only when it's
        # been changed from whatever the client's own default happens to be
        # (even that default - e.g. HQ's account - is still money moving
        # between businesses).
        context["always_confirm_bank_account"] = client.get("client_type") == "Franchise"

        if not customer_name and client.get("billing_contact"):
            context["customer_name"] = client.get("billing_contact")
            context["customer_label"] = _customer_display_name(client.get("billing_contact"))
            context["contact_email"] = _customer_email(client.get("billing_contact"))

    return context


# =====================================================
# LINK OPTIONS
# =====================================================

@frappe.whitelist()
def get_link_options(doctype, txt=None, limit_page_length=200):
    _require_logged_in_user()

    if not doctype:
        return []

    try:
        limit_page_length = int(limit_page_length or 200)
    except Exception:
        limit_page_length = 200

    limit_page_length = min(max(limit_page_length, 1), 1000)

    filters = {}

    if txt:
        filters["name"] = ["like", f"%{txt}%"]

    if doctype == "Client":
        allowed_clients = _get_allowed_clients_for_user()

        if allowed_clients is not None:
            if not allowed_clients:
                return []

            filters["name"] = ["in", allowed_clients]

        meta = frappe.get_meta("Client")
        fields = ["name"]

        for fieldname in ["full_name", "name1", "first_name", "last_name", "preferred_name"]:
            if meta.has_field(fieldname):
                fields.append(fieldname)

        if meta.has_field("full_name"):
            order_by = "full_name asc, name asc"
        elif meta.has_field("name1"):
            order_by = "name1 asc, last_name asc, name asc" if meta.has_field("last_name") else "name1 asc, name asc"
        else:
            order_by = "name asc"

        rows = frappe.get_all(
            "Client",
            filters=filters,
            fields=fields,
            order_by=order_by,
            limit_page_length=limit_page_length,
            ignore_permissions=True,
        )

        return [
            {
                "name": row.get("name"),
                "label": _client_display_from_row(row),
            }
            for row in rows
        ]

    if doctype == "Customer":
        rows = frappe.get_all(
            "Customer",
            filters=filters,
            fields=["name", "customer_name"],
            order_by="customer_name asc, name asc",
            limit_page_length=limit_page_length,
            ignore_permissions=True,
        )

        return [
            {
                "name": row.get("name"),
                "label": row.get("customer_name") or row.get("name"),
            }
            for row in rows
        ]

    if doctype == "Item":
        rows = frappe.get_all(
            "Item",
            filters=filters,
            fields=["name", "item_name", "description", "stock_uom"],
            order_by="name asc",
            limit_page_length=limit_page_length,
            ignore_permissions=True,
        )

        return [
            {
                "name": row.get("name"),
                "label": row.get("item_name") or row.get("name"),
                "description": row.get("description") or "",
                "uom": row.get("stock_uom") or "",
                "bundle_session_count": _get_billable_session_count_for_item(row.get("name")),
            }
            for row in rows
        ]

    rows = frappe.get_all(
        doctype,
        filters=filters,
        fields=["name"],
        order_by="name asc",
        limit_page_length=limit_page_length,
        ignore_permissions=True,
    )

    return [{"name": row.get("name"), "label": row.get("name")} for row in rows]


# =====================================================
# CLIENT DEFAULTS / ITEM DETAILS
# =====================================================

@frappe.whitelist()
def get_client_invoice_defaults(client_name=None):
    _require_logged_in_user()

    client_name = (client_name or "").strip()

    if not client_name:
        return {}

    if not _current_user_can_access_client(client_name):
        frappe.throw(_("You do not have permission to invoice this client."), frappe.PermissionError)

    if not frappe.db.exists("Client", client_name):
        frappe.throw(_("Client not found."))

    client = frappe.get_doc("Client", client_name)

    billing_contact = client.get("billing_contact") or ""
    billing_contact_label = _customer_display_name(billing_contact)
    contact_email = _customer_email(billing_contact)

    open_balances = []

    if _has_doctype("Client Package Balance"):
        open_balances = frappe.get_all(
            "Client Package Balance",
            filters=[
                ["client", "=", client_name],
                ["status", "=", "Active"],
                ["qty_available", ">", 0],
            ],
            fields=["name", "service_item", "qty_available", "sales_invoice"],
            order_by="creation asc",
            limit_page_length=20,
            ignore_permissions=True,
        )

    client_type = client.get("client_type") or ""
    allow_bank_override = client_type in BANK_OVERRIDE_CLIENT_TYPES

    return {
        "client_name": client_name,
        "client_label": _client_display_name(client_name),
        "billing_contact": billing_contact,
        "billing_contact_label": billing_contact_label,
        "contact_email": contact_email,
        "price_list": client.get("pricelist") or "",
        "company": client.get("company") or "",
        "coach_label": _coach_label_from_name(client.get("attending_coach") or client.get("primary_coach") or ""),
        "bank_account": client.get("banking") or "",
        "client_bank_account": client.get("banking") or "",
        "bank_display_text": _bank_display_text(client.get("banking") or ""),
        "allow_bank_override": allow_bank_override,
        "bank_account_options": (
            _ensure_default_bank_account_option(_get_bank_account_options(), client.get("banking") or "")
            if allow_bank_override else []
        ),
        "always_confirm_bank_account": client_type == "Franchise",
        "travel_charged": int(client.get("travel_charged") or 0),
        "travel_miles_one_way": float(client.get("travel_miles_one_way") or 0),
        "travel_charge_per_session": float(client.get("travel_charge_per_session") or 0),
        "open_balances": open_balances,
    }


@frappe.whitelist()
def resolve_invoice_context(client_name=None, customer_name=None):
    _require_logged_in_user()

    client_name = (client_name or "").strip()

    if client_name and not _current_user_can_access_client(client_name):
        frappe.throw(_("You do not have permission to access this client."), frappe.PermissionError)

    return _resolve_invoice_context(client_name, customer_name)


@frappe.whitelist()
def get_item_details_for_invoice(item_code=None, company=None, customer=None, price_list=None):
    _require_logged_in_user()

    return _item_defaults(
        item_code=item_code,
        company=company,
        customer=customer,
        price_list=price_list,
    )


@frappe.whitelist()
def calculate_invoice_travel(client_name=None, items=None):
    _require_logged_in_user()

    client_name = (client_name or "").strip()

    if client_name and not _current_user_can_access_client(client_name):
        frappe.throw(_("You do not have permission to access this client."), frappe.PermissionError)

    payload_items = _parse_payload(items)
    total_sessions = _get_total_billable_sessions_from_payload(payload_items)
    travel_row = _build_travel_row_for_client(client_name, total_sessions)

    return {
        "total_sessions": total_sessions,
        "travel_row": travel_row,
    }


# =====================================================
# SAVE / SUBMIT HELPERS
# =====================================================

def _set_invoice_header_fields(doc, payload):
    doc.customer = (payload.get("customer") or "").strip() or None
    doc.custom_client = (payload.get("custom_client") or "").strip() or None
    posting_date = payload.get("posting_date") or doc.posting_date or nowdate()

    doc.posting_date = posting_date
    doc.due_date = payload.get("due_date") or doc.due_date or posting_date or nowdate()
    
    if doc.meta.has_field("set_posting_time"):
        doc.set_posting_time = 1

    if not doc.naming_series:
        doc.naming_series = _default_naming_series()

    context = _resolve_invoice_context(doc.custom_client, doc.customer)

    if context.get("company"):
        doc.company = context.get("company")

    if context.get("price_list"):
        doc.selling_price_list = context.get("price_list")

    if doc.customer:
        doc.customer_name = _customer_display_name(doc.customer)

    if doc.meta.has_field("custom_bank_account"):
        submitted_bank_account = (payload.get("bank_account") or "").strip()

        if context.get("allow_bank_override") and submitted_bank_account:
            doc.custom_bank_account = submitted_bank_account
        else:
            doc.custom_bank_account = context.get("bank_account") or ""

        # Franchise-type clients (representing a coach, for cross-coach/HQ
        # invoicing) often have no company of their own set at all - the
        # invoice's company should follow whichever coach's bank account is
        # actually on it (that coach's own business), not just rely on the
        # client record's own (possibly blank) company field.
        if doc.custom_bank_account:
            bank_owner_coach = _get_bank_account_owner_coach(doc.custom_bank_account)
            bank_owner_company = _get_coach_company(bank_owner_coach) if bank_owner_coach else ""

            if bank_owner_company:
                doc.company = bank_owner_company

    if context.get("contact_email"):
        doc.contact_email = context.get("contact_email")

    current_coach = _get_current_coach()
    current_coach_name = current_coach.get("name") if current_coach else ""

    meta = frappe.get_meta("Sales Invoice")

    if meta.has_field("disable_rounded_total"):
        # The Currency/Company "round off" settings on this site round the
        # total to the nearest whole pound (e.g. £35.80 -> £36), which then
        # makes outstanding_amount wrong too - a coach trying to record the
        # actual £35.80 payment gets told it must be £36. Dashboard invoices
        # should always track the exact line-item total, in pounds and
        # pence, never rounded to a whole pound.
        doc.disable_rounded_total = 1
        doc.rounding_adjustment = 0
        doc.base_rounding_adjustment = 0

    if meta.has_field("custom_created_by_coach") and current_coach_name and not doc.get("custom_created_by_coach"):
        doc.custom_created_by_coach = current_coach_name

    if meta.has_field("custom_income_owner_coach") and doc.custom_client:
        # An overridden bank account (e.g. Emily invoicing on SJ's behalf
        # with her own account) means the income belongs to whichever coach
        # owns that account, not the client's usual primary coach - it's
        # Emily's business, so it needs to show up on Emily's dashboard and
        # be recorded as hers, not SJ's.
        override_owner = ""
        if doc.meta.has_field("custom_bank_account") and doc.get("custom_bank_account"):
            override_owner = _get_bank_account_owner_coach(doc.custom_bank_account)

        if override_owner:
            doc.custom_income_owner_coach = override_owner
        else:
            client_primary = frappe.db.get_value("Client", doc.custom_client, "primary_coach")
            if client_primary:
                doc.custom_income_owner_coach = client_primary


def _set_invoice_items(doc, items_payload):
    price_list = doc.selling_price_list or ""
    doc.set("items", [])

    final_items = _with_auto_travel_items(doc.custom_client, items_payload)

    for row in final_items or []:
        item_code = (row.get("item_code") or "").strip()

        if not item_code:
            continue

        defaults = _item_defaults(
            item_code=item_code,
            company=doc.company,
            customer=doc.customer,
            price_list=price_list,
        )

        qty = _to_float(row.get("qty")) or 1
        rate = _to_float(row.get("rate"))

        if not rate:
            rate = defaults.get("rate") or 0

        description = (row.get("description") or "").strip() or defaults.get("description") or item_code

        child = doc.append("items", {})
        child.item_code = item_code
        child.item_name = defaults.get("item_name") or item_code
        child.description = description
        child.qty = qty
        child.rate = rate
        child.uom = defaults.get("uom") or ""
        child.stock_uom = defaults.get("uom") or ""
        child.conversion_factor = 1
        child.amount = qty * rate


def _validate_invoice(doc):
    if not doc.customer:
        frappe.throw(_("Billing Contact is required."))

    if not doc.custom_client:
        frappe.throw(_("Client is required."))

    if not _current_user_can_access_client(doc.custom_client):
        frappe.throw(_("You do not have permission to invoice this client."), frappe.PermissionError)

    if not doc.company:
        frappe.throw(_("Company could not be resolved from the selected Client."))

    if not doc.posting_date:
        frappe.throw(_("Posting Date is required."))

    if not doc.due_date:
        frappe.throw(_("Due Date is required."))

    if not doc.selling_price_list:
        frappe.throw(_("Price List could not be resolved from the selected Client."))

    if not doc.items:
        frappe.throw(_("At least one invoice item is required."))

    has_negative_line = any(
        _to_float(item.rate) < 0 or _to_float(item.amount) < 0
        for item in doc.items
    )

    if has_negative_line and not _is_franchisor_user():
        frappe.throw(_("Only HQ/Office can add a negative amount to an invoice."), frappe.PermissionError)


def _prepare_invoice_for_save(doc):
    if hasattr(doc, "set_missing_values"):
        doc.set_missing_values()

    if hasattr(doc, "calculate_taxes_and_totals"):
        doc.calculate_taxes_and_totals()


def _create_client_packages_from_invoice(doc):
    client = doc.get("custom_client")

    if not client:
        return

    if not _has_doctype("Client Package") or not _has_doctype("Client Package Balance"):
        return

    package_count = 0

    for invoice_item in doc.get("items") or []:
        item_code = invoice_item.get("item_code")

        if not item_code or item_code == TRAVEL_ITEM_CODE:
            continue

        existing_package = frappe.get_all(
            "Client Package",
            filters={
                "sales_invoice": doc.name,
                "sales_invoice_item": invoice_item.name,
            },
            fields=["name"],
            limit_page_length=1,
            ignore_permissions=True,
        )

        if existing_package:
            continue

        package_rows = []

        product_bundle_name = frappe.db.get_value(
            "Product Bundle",
            {
                "new_item_code": item_code,
                "disabled": 0,
            },
            "name",
        )

        if product_bundle_name:
            product_bundle = frappe.get_doc("Product Bundle", product_bundle_name)

            for bundle_item in product_bundle.get("items") or []:
                service_item = bundle_item.get("item_code")
                qty = float(bundle_item.get("qty") or 0) * float(invoice_item.get("qty") or 1)

                if service_item and qty > 0:
                    if service_item == PARENT_CHECKIN_ITEM_CODE and not _client_includes_parent_checkins(client):
                        continue
                    package_rows.append({
                        "service_item": service_item,
                        "qty": qty,
                    })

        elif item_code in SINGLE_SESSION_ITEMS:
            package_rows.append({
                "service_item": item_code,
                "qty": float(invoice_item.get("qty") or 1),
            })

        if not package_rows:
            continue

        package = frappe.new_doc("Client Package")
        package.naming_series = "TRK-PKG-.YYYY.-.#####"
        package.client = client
        package.package_item = item_code
        package.sales_invoice = doc.name
        package.sales_invoice_item = invoice_item.name
        package.company = doc.get("company")
        package.posting_date = doc.get("posting_date")
        package.invoice_status = doc.get("status")
        package.outstanding_amount = doc.get("outstanding_amount") or 0
        package.status = "Active"
        package.notes = "Created automatically from Sales Invoice " + doc.name
        package.insert(ignore_permissions=True)

        package_count += 1

        for row in package_rows:
            balance = frappe.new_doc("Client Package Balance")
            balance.client_package = package.name
            balance.client = client
            balance.service_item = row["service_item"]
            balance.qty_purchased = row["qty"]
            balance.qty_booked = 0
            balance.qty_used = 0
            balance.qty_available = row["qty"]
            balance.status = "Active"
            balance.sales_invoice = doc.name
            balance.invoice_status = doc.get("status")
            balance.outstanding_amount = doc.get("outstanding_amount") or 0
            balance.parent_checkins_due = 0
            balance.last_booking_warning_sent = 0
            balance.insert(ignore_permissions=True)

    return package_count


def _serialize_invoice(doc):
    context = _resolve_invoice_context(doc.custom_client, doc.customer)

    return {
        "name": doc.name,
        "docstatus": doc.docstatus,
        "status": doc.status or ("Draft" if doc.docstatus == 0 else "Submitted" if doc.docstatus == 1 else "Cancelled"),
        "customer": doc.customer or "",
        "custom_client": doc.custom_client or "",
        "posting_date": str(doc.posting_date or ""),
        "due_date": str(doc.due_date or ""),
        "naming_series": doc.naming_series or "",
        "company": doc.company or context.get("company") or "",
        "contact_email": doc.contact_email or context.get("contact_email") or "",
        "grand_total": doc.grand_total or 0,
        "outstanding_amount": doc.outstanding_amount or 0,
        "paid_amount": doc.paid_amount or 0,
        "client_label": context.get("client_label") or "",
        "customer_label": context.get("customer_label") or "",
        "price_list": doc.selling_price_list or context.get("price_list") or "",
        "coach_label": context.get("coach_label") or "",
        "bank_account": (doc.get("custom_bank_account") if doc.meta.has_field("custom_bank_account") else "") or context.get("bank_account") or "",
        "client_bank_account": context.get("client_bank_account") or "",
        "bank_display_text": context.get("bank_display_text") or "",
        "allow_bank_override": context.get("allow_bank_override") or False,
        "bank_account_options": context.get("bank_account_options") or [],
        "always_confirm_bank_account": context.get("always_confirm_bank_account") or False,
        "items": [
            {
                "item_code": row.item_code or "",
                "item_name": row.item_name or "",
                "description": row.description or "",
                "qty": row.qty or 0,
                "rate": row.rate or 0,
                "amount": row.amount or 0,
                "uom": row.uom or "",
            }
            for row in (doc.items or [])
        ],
    }


# =====================================================
# SAVE / SUBMIT / EMAIL API
# =====================================================

@frappe.whitelist()
def save_draft_invoice(docname=None, data=None):
    _require_logged_in_user()

    payload = _parse_payload(data)
    items_payload = payload.get("items") or []

    if docname:
        if not _current_user_can_access_invoice(docname):
            frappe.throw(_("You do not have permission to edit this invoice."), frappe.PermissionError)

        doc = frappe.get_doc("Sales Invoice", docname)

        if doc.docstatus != 0:
            frappe.throw(_("Only draft invoices can be edited from the dashboard."))
    else:
        doc = frappe.new_doc("Sales Invoice")

    _set_invoice_header_fields(doc, payload)
    _set_invoice_items(doc, items_payload)
    _validate_invoice(doc)
    _prepare_invoice_for_save(doc)

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    doc.reload()
    return _serialize_invoice(doc)


@frappe.whitelist()
def submit_invoice(docname=None, data=None):
    _require_logged_in_user()

    payload = _parse_payload(data)
    items_payload = payload.get("items") or []

    if docname:
        if not _current_user_can_access_invoice(docname):
            frappe.throw(_("You do not have permission to submit this invoice."), frappe.PermissionError)

        doc = frappe.get_doc("Sales Invoice", docname)
    else:
        doc = frappe.new_doc("Sales Invoice")

    if doc.docstatus != 0:
        frappe.throw(_("Only draft invoices can be submitted from the dashboard."))

    _set_invoice_header_fields(doc, payload)
    _set_invoice_items(doc, items_payload)
    _validate_invoice(doc)
    _prepare_invoice_for_save(doc)

    if not doc.name:
        doc.save(ignore_permissions=True)

    doc.submit()
    _create_client_packages_from_invoice(doc)
    frappe.db.commit()

    doc.reload()
    return _serialize_invoice(doc)


def _current_user_phone():
    user = frappe.session.user

    if not user or user == "Guest":
        return ""

    meta = frappe.get_meta("User")

    for fieldname in ("mobile_no", "phone", "phone_no"):
        if meta.has_field(fieldname):
            value = frappe.db.get_value("User", user, fieldname)
            if value:
                return value

    return ""


@frappe.whitelist()
def get_invoice_email_defaults(docname=None, template_name=None):
    """
    Subject/message the compose modal pre-fills before a coach edits and
    sends - rendered from an Email Template (desk -> Email Template) when
    one exists, so wording can be changed there without a code deploy.
    Falls back to a hardcoded default otherwise. template_name lets a
    caller pick any Email Template on the site (see the Client Details
    "Send Invoice" button, which offers a full list via
    email_templates.get_email_template_options) rather than always using
    the one this app seeds.
    """
    _require_logged_in_user()

    if not docname:
        frappe.throw(_("Invoice is required."))

    if not _current_user_can_access_invoice(docname):
        frappe.throw(_("You do not have permission to access this invoice."), frappe.PermissionError)

    doc = frappe.get_doc("Sales Invoice", docname)
    serialized = _serialize_invoice(doc)

    current_user_email = frappe.session.user if "@" in (frappe.session.user or "") else ""

    context = {
        "customer_name": serialized.get("customer_label") or "Billing Contact",
        "invoice_number": doc.name,
        "amount_due": f"{_to_float(doc.outstanding_amount):.2f}",
        "due_date": frappe.utils.formatdate(doc.due_date, "dd-MM-yyyy") if doc.due_date else "",
        "bank_details": serialized.get("bank_display_text") or "Bank details available on request.",
        "coach_name": serialized.get("coach_label") or "Coach",
        "company_label": serialized.get("company") or "The Resilient Kid",
        "coach_email": current_user_email,
        "coach_phone": _current_user_phone(),
    }

    fallback_message = (
        "Hi {{ customer_name }},\n"
        "\n"
        "I hope you're doing well.\n"
        "\n"
        "Please find attached your invoice.\n"
        "\n"
        "Invoice number: {{ invoice_number }}\n"
        "Amount due: £{{ amount_due }}\n"
        "Payment due by: {{ due_date }}\n"
        "\n"
        "Payment details:\n"
        "{{ bank_details }}\n"
        "\n"
        "Warm regards,\n"
        "{{ coach_name }}\n"
        "{{ company_label }}"
        "{% if coach_email %}\n\n{{ coach_email }}{% endif %}"
        "{% if coach_phone %}\n{{ coach_phone }}{% endif %}"
    )

    subject, message = render_email(
        (template_name or "").strip() or INVOICE_EMAIL_TEMPLATE,
        context,
        fallback_subject="Invoice {{ invoice_number }}",
        fallback_message=fallback_message,
    )

    return {"subject": subject, "message": message}


@frappe.whitelist()
def get_client_email_defaults(client_name=None, template_name=None):
    """
    Subject/message for the generic "Send Email" button on the Client
    Details page - not tied to any invoice or PDF attachment, just a
    plain email to the client rendered from whichever Email Template is
    picked (see email_templates.get_email_template_options).
    """
    _require_logged_in_user()

    client_name = (client_name or "").strip()

    if not client_name:
        frappe.throw(_("Client is required."))

    if not _current_user_can_access_client(client_name):
        frappe.throw(_("You do not have permission to access this client."), frappe.PermissionError)

    if not frappe.db.exists("Client", client_name):
        frappe.throw(_("Client not found."))

    context_data = _resolve_invoice_context(client_name, None)
    current_user_email = frappe.session.user if "@" in (frappe.session.user or "") else ""

    context = {
        "client_name": _client_display_name(client_name),
        "contact_name": context_data.get("customer_label") or _client_display_name(client_name),
        "coach_name": context_data.get("coach_label") or "Coach",
        "company_label": context_data.get("company") or "The Resilient Kid",
        "coach_email": current_user_email,
        "coach_phone": _current_user_phone(),
    }

    fallback_message = (
        "Hi {{ contact_name }},\n"
        "\n"
        "\n"
        "\n"
        "Warm regards,\n"
        "{{ coach_name }}\n"
        "{{ company_label }}"
        "{% if coach_email %}\n\n{{ coach_email }}{% endif %}"
        "{% if coach_phone %}\n{{ coach_phone }}{% endif %}"
    )

    subject, message = render_email(
        (template_name or "").strip(),
        context,
        fallback_subject="A message from {{ company_label }}",
        fallback_message=fallback_message,
    )

    return {"subject": subject, "message": message}


@frappe.whitelist()
def send_client_email(client_name=None, recipient=None, subject=None, message=None, cc=None, sender=None):
    """Sends the "Send Email" compose modal's contents - no PDF, no invoice involved."""
    _require_logged_in_user()

    client_name = (client_name or "").strip()
    recipient = (recipient or "").strip()

    if not client_name:
        frappe.throw(_("Client is required."))

    if not _current_user_can_access_client(client_name):
        frappe.throw(_("You do not have permission to email this client."), frappe.PermissionError)

    if not recipient:
        frappe.throw(_("Recipient email is required."))

    subject = (subject or "Message").strip()
    message = plain_text_to_email_html((message or "").strip())

    kwargs = {
        "recipients": [recipient],
        "subject": subject,
        "message": message,
        "now": True,
    }

    cc_list = parse_email_list(cc)
    if cc_list:
        kwargs["cc"] = cc_list

    sender = (sender or "").strip()
    if sender:
        kwargs["sender"] = sender

    frappe.sendmail(**kwargs)

    return {"ok": 1}


@frappe.whitelist()
def get_client_email_options(client_name=None):
    """
    The two email addresses "Send Email" can offer: the client's own
    email (if they have one on file) and their billing contact's email -
    Ashley's own wording for these is "client email" vs "contact email".
    """
    _require_logged_in_user()

    client_name = (client_name or "").strip()

    if not client_name:
        frappe.throw(_("Client is required."))

    if not _current_user_can_access_client(client_name):
        frappe.throw(_("You do not have permission to access this client."), frappe.PermissionError)

    if not frappe.db.exists("Client", client_name):
        return []

    client = frappe.get_doc("Client", client_name)
    options = []

    client_email = (client.get("email") or "").strip() if client.meta.has_field("email") else ""
    if client_email:
        options.append({"value": client_email, "label": f"Client email ({client_email})"})

    billing_contact = client.get("billing_contact") or ""
    contact_email = _customer_email(billing_contact) if billing_contact else ""

    if contact_email and contact_email != client_email:
        options.append({"value": contact_email, "label": f"Contact email ({contact_email})"})

    return options


@frappe.whitelist()
def send_invoice_email(docname, recipient=None, reply_to=None, subject=None, message=None, cc=None, sender=None):
    _require_logged_in_user()

    if not docname:
        frappe.throw(_("Invoice is required."))

    if not _current_user_can_access_invoice(docname):
        frappe.throw(_("You do not have permission to email this invoice."), frappe.PermissionError)

    doc = frappe.get_doc("Sales Invoice", docname)

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted invoices can be emailed."))

    recipient = (recipient or doc.contact_email or _customer_email(doc.customer) or "").strip()

    if not recipient:
        frappe.throw(_("Recipient email is required."))

    subject = (subject or f"Invoice {doc.name}").strip()
    message = (message or f"Please find attached invoice {doc.name}.").strip()
    message = plain_text_to_email_html(message)

    reply_to = (reply_to or "").strip()

    attachments = [
        frappe.attach_print(
            "Sales Invoice",
            doc.name,
            letterhead="Resilient Kid",
        )
    ]

    kwargs = {
        "recipients": [recipient],
        "subject": subject,
        "message": message,
        "attachments": attachments,
        "reference_doctype": "Sales Invoice",
        "reference_name": doc.name,
    }

    if reply_to:
        kwargs["reply_to"] = reply_to

    cc_list = parse_email_list(cc)
    if cc_list:
        kwargs["cc"] = cc_list

    sender = (sender or "").strip()
    if sender:
        kwargs["sender"] = sender

    frappe.sendmail(**kwargs)

    return {"ok": 1}

def _get_bank_account_gl_account(bank_account_name):
    if not bank_account_name or not frappe.db.exists("Bank Account", bank_account_name):
        frappe.throw(_("Please select a valid bank account."))

    bank_account = frappe.get_doc("Bank Account", bank_account_name)

    for fieldname in ["account", "custom_account", "ledger_account", "default_account"]:
        if bank_account.meta.has_field(fieldname) and bank_account.get(fieldname):
            return bank_account.get(fieldname)

    frappe.throw(
        _("Bank Account {0} does not have a linked ledger account. Please add the Account field to the Bank Account record.")
        .format(bank_account_name)
    )


@frappe.whitelist()
def allocate_invoice_payment(invoice_name=None, posting_date=None, amount=None, bank_account=None, reference_no=None):
    _require_logged_in_user()

    if not invoice_name:
        frappe.throw(_("Invoice is required."))

    if not _current_user_can_access_invoice(invoice_name):
        frappe.throw(_("You do not have permission to allocate payment to this invoice."), frappe.PermissionError)

    invoice = frappe.get_doc("Sales Invoice", invoice_name)

    if invoice.docstatus != 1:
        frappe.throw(_("Only submitted invoices can have payments allocated."))

    outstanding = payment_utils.get_outstanding_amount_for_payment(
        invoice.outstanding_amount, invoice.grand_total, invoice_name
    )
    payment_amount = flt(amount, 2)

    if payment_amount <= 0:
        frappe.throw(_("Payment amount must be greater than zero."))

    if payment_amount > outstanding:
        frappe.throw(_("Payment amount cannot be more than the outstanding amount ({0}).").format(outstanding))

    client_bank_account = ""

    if invoice.meta.has_field("custom_bank_account") and invoice.get("custom_bank_account"):
        # An invoice-specific override (e.g. Emily invoicing on SJ's behalf
        # with her own bank account) takes priority over the client's own
        # default - whoever's account is on the invoice is who gets paid.
        client_bank_account = invoice.get("custom_bank_account")
    elif invoice.get("custom_client"):
        client_bank_account = frappe.db.get_value(
            "Client",
            invoice.get("custom_client"),
            "banking",
        )

    if not client_bank_account:
        frappe.throw(_("No bank account is selected on this invoice's client."))

    paid_to_account = _get_bank_account_gl_account(client_bank_account)

    payment = payment_utils.build_and_submit_payment_entry(
        invoice_name=invoice.name,
        paid_to_account=paid_to_account,
        payment_date=posting_date or nowdate(),
        remarks=f"Payment allocated from dashboard invoice details for {invoice.name}",
        final_amount=payment_amount,
        reference_no=reference_no or invoice.name,
    )

    invoice.reload()

    return {
        "payment_entry": payment.name,
        "invoice": invoice.name,
        "status": invoice.status,
        "paid_amount": invoice.paid_amount,
        "outstanding_amount": invoice.outstanding_amount,
        "grand_total": invoice.grand_total,
    }

