import json
import frappe
from frappe import _
from frappe.utils import nowdate


FRANCHISOR_USERS = [
    "ashley@theresilientkid.co.uk",
    "hq@theresilientkid.co.uk",
    "office@theresilientpeople.uk",
]

COACH_DASHBOARD = "coach"
FRANCHISOR_DASHBOARD = "franchisor"

TRAVEL_ITEM_CODE = "TRA002"
TRAVEL_RATE_PER_MILE = 0.45
FREE_MILES_ONE_WAY = 10
SINGLE_SESSION_ITEMS = ["COA001", "FAM001", "INI001", "PAR001"]


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

    return frappe.db.get_value("Customer", customer_name, "email_id") or ""


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
        ["primary_coach", "attending_coach"],
        as_dict=True,
    )

    if not client:
        return False

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

    return {
        "name": row.get("name"),
        "posting_date": str(row.get("posting_date") or ""),
        "due_date": str(row.get("due_date") or ""),
        "custom_client": client_name or "",
        "client_name": _client_display_from_row(client_row) if client_row else row.get("customer_name") or row.get("customer") or "—",
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
    if not item_code or item_code == TRAVEL_ITEM_CODE:
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

            if service_item and service_item != TRAVEL_ITEM_CODE:
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
    one_way_miles = _to_float(client.get("travel_miles_one_way"))

    if not travel_charged or one_way_miles <= FREE_MILES_ONE_WAY:
        return None

    chargeable_one_way = one_way_miles - FREE_MILES_ONE_WAY
    chargeable_return_miles = chargeable_one_way * 2
    travel_qty = chargeable_return_miles * total_sessions

    description = (
        f"Travel: {one_way_miles:g} miles each way, less "
        f"{FREE_MILES_ONE_WAY:g} free miles each way = "
        f"{chargeable_one_way:g} chargeable miles each way "
        f"({chargeable_return_miles:g} miles return) x £{TRAVEL_RATE_PER_MILE:g} "
        f"x {total_sessions:g} sessions"
    )

    return {
        "item_code": TRAVEL_ITEM_CODE,
        "description": description,
        "qty": travel_qty,
        "rate": TRAVEL_RATE_PER_MILE,
    }


def _with_auto_travel_items(client_name, items_payload):
    cleaned_items = []

    for row in items_payload or []:
        if (row.get("item_code") or "").strip() == TRAVEL_ITEM_CODE:
            continue

        cleaned_items.append(row)

    total_sessions = _get_total_billable_sessions_from_payload(cleaned_items)
    travel_row = _build_travel_row_for_client(client_name, total_sessions)

    if travel_row:
        cleaned_items.append(travel_row)

    return cleaned_items


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
        "bank_display_text": "",
        "contact_email": _customer_email(customer_name),
    }

    if client_name and frappe.db.exists("Client", client_name):
        client = frappe.get_doc("Client", client_name)

        context["company"] = client.get("company") or ""
        context["price_list"] = client.get("pricelist") or ""
        context["coach_label"] = _coach_label_from_name(client.get("attending_coach") or client.get("primary_coach") or "")
        context["bank_display_text"] = _bank_display_text(client.get("banking") or "")

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

    return {
        "client_name": client_name,
        "client_label": _client_display_name(client_name),
        "billing_contact": billing_contact,
        "billing_contact_label": billing_contact_label,
        "contact_email": contact_email,
        "price_list": client.get("pricelist") or "",
        "company": client.get("company") or "",
        "coach_label": _coach_label_from_name(client.get("attending_coach") or client.get("primary_coach") or ""),
        "bank_display_text": _bank_display_text(client.get("banking") or ""),
        "travel_charged": int(client.get("travel_charged") or 0),
        "travel_miles_one_way": float(client.get("travel_miles_one_way") or 0),
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
    doc.posting_date = payload.get("posting_date") or doc.posting_date or nowdate()
    doc.due_date = payload.get("due_date") or doc.due_date or doc.posting_date or nowdate()

    if not doc.naming_series:
        doc.naming_series = _default_naming_series()

    context = _resolve_invoice_context(doc.custom_client, doc.customer)

    if context.get("company"):
        doc.company = context.get("company")

    if context.get("price_list"):
        doc.selling_price_list = context.get("price_list")

    if doc.customer:
        doc.customer_name = _customer_display_name(doc.customer)

    if context.get("contact_email"):
        doc.contact_email = context.get("contact_email")

    current_coach = _get_current_coach()
    current_coach_name = current_coach.get("name") if current_coach else ""

    meta = frappe.get_meta("Sales Invoice")

    if meta.has_field("custom_created_by_coach") and current_coach_name and not doc.get("custom_created_by_coach"):
        doc.custom_created_by_coach = current_coach_name

    if meta.has_field("custom_income_owner_coach") and doc.custom_client:
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
        "bank_display_text": context.get("bank_display_text") or "",
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


@frappe.whitelist()
def send_invoice_email(docname, recipient=None, reply_to=None, subject=None, message=None):
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
    message = "<p>" + "</p><p>".join(
        line.strip() for line in message.splitlines() if line.strip()
    ) + "</p>"
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
def get_payment_bank_accounts(invoice_name=None):
    _require_logged_in_user()

    if not invoice_name:
        frappe.throw(_("Invoice is required."))

    if not _current_user_can_access_invoice(invoice_name):
        frappe.throw(_("You do not have permission to access this invoice."), frappe.PermissionError)

    invoice = frappe.get_doc("Sales Invoice", invoice_name)

    default_bank = ""

    if invoice.get("custom_client") and frappe.db.exists("Client", invoice.get("custom_client")):
        default_bank = frappe.db.get_value("Client", invoice.get("custom_client"), "banking") or ""

    rows = frappe.get_all(
        "Bank Account",
        fields=["name", "bank_account_name", "bank"],
        order_by="bank_account_name asc, name asc",
        limit_page_length=500,
        ignore_permissions=True,
    )

    return {
        "default_bank_account": default_bank,
        "bank_accounts": [
            {
                "name": row.name,
                "label": row.bank_account_name or row.bank or row.name,
            }
            for row in rows
        ],
    }


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

    outstanding = _to_float(invoice.outstanding_amount)
    payment_amount = _to_float(amount)

    if payment_amount <= 0:
        frappe.throw(_("Payment amount must be greater than zero."))

    if payment_amount > outstanding:
        frappe.throw(_("Payment amount cannot be more than the outstanding amount."))

    paid_to_account = _get_bank_account_gl_account(bank_account)

    payment = frappe.new_doc("Payment Entry")
    payment.payment_type = "Receive"
    payment.posting_date = posting_date or nowdate()
    payment.company = invoice.company
    payment.party_type = "Customer"
    payment.party = invoice.customer
    payment.party_name = invoice.customer_name
    payment.paid_amount = payment_amount
    payment.received_amount = payment_amount
    payment.paid_to = paid_to_account
    payment.reference_no = reference_no or invoice.name
    payment.reference_date = posting_date or nowdate()

    payment.append("references", {
        "reference_doctype": "Sales Invoice",
        "reference_name": invoice.name,
        "allocated_amount": payment_amount,
        "total_amount": invoice.grand_total,
        "outstanding_amount": outstanding,
    })

    if payment.meta.has_field("custom_bank_account"):
        payment.custom_bank_account = bank_account

    if payment.meta.has_field("custom_client"):
        payment.custom_client = invoice.get("custom_client")

    if payment.meta.has_field("custom_income_owner_coach") and invoice.meta.has_field("custom_income_owner_coach"):
        payment.custom_income_owner_coach = invoice.get("custom_income_owner_coach")

    payment.insert(ignore_permissions=True)
    payment.submit()

    frappe.db.commit()

    invoice.reload()

    return {
        "payment_entry": payment.name,
        "invoice": invoice.name,
        "status": invoice.status,
        "paid_amount": invoice.paid_amount,
        "outstanding_amount": invoice.outstanding_amount,
        "grand_total": invoice.grand_total,
    }
