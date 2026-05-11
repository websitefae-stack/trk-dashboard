import json
import frappe
from frappe import _
from frappe.utils import nowdate

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared import invoices as invoice_api


def _naming_series_default():
    meta = frappe.get_meta("Sales Invoice")
    df = meta.get_field("naming_series")
    if not df:
        return ""

    options = [row.strip() for row in (df.options or "").split("\n") if row.strip()]
    return options[0] if options else ""


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


def _get_customer_label(customer_name):
    if not customer_name:
        return ""

    if frappe.db.exists("Customer", customer_name):
        return frappe.db.get_value("Customer", customer_name, "customer_name") or customer_name

    return customer_name


def _get_client_label(client_name):
    if not client_name:
        return ""

    return invoice_api._client_display_name(client_name)


def _get_initial_client_defaults(doc):
    if not doc or not doc.get("custom_client"):
        return {}

    try:
        return invoice_api.get_client_invoice_defaults(doc.get("custom_client")) or {}
    except Exception:
        frappe.log_error(frappe.get_traceback(), "franchisor invoice_details initial client defaults failed")
        return {}


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    context.no_cache = 1
    context.active_page = "invoices"
    context.dashboard_base_path = "/franchisor_db"

    requested_name = (frappe.form_dict.get("name") or "").strip()
    is_new = str(frappe.form_dict.get("new") or "").lower() in ("1", "true", "yes") or not requested_name

    if is_new:
        doc = frappe.new_doc("Sales Invoice")
        doc.posting_date = nowdate()
        doc.due_date = nowdate()
        doc.naming_series = _naming_series_default()
        docname = ""
    else:
        if not invoice_api._current_user_can_access_invoice(requested_name):
            frappe.throw(_("You do not have permission to access this invoice."), frappe.PermissionError)

        doc = frappe.get_doc("Sales Invoice", requested_name)
        docname = doc.name

    resolved = invoice_api._resolve_invoice_context(doc.custom_client, doc.customer)
    client_defaults = _get_initial_client_defaults(doc)

    billing_contact = doc.customer or client_defaults.get("billing_contact") or ""
    billing_contact_label = (
        client_defaults.get("billing_contact_label")
        or resolved.get("customer_label")
        or _get_customer_label(billing_contact)
    )

    context.doc = doc
    context.docname = docname
    context.is_new = 1 if is_new else 0
    context.page_title = doc.name or "New Invoice"

    context.current_user_email = frappe.session.user if "@" in (frappe.session.user or "") else ""
    context.current_user_phone = _current_user_phone()

    context.client_label = resolved.get("client_label") or _get_client_label(doc.custom_client) or ""
    context.customer_label = billing_contact_label or ""
    context.billing_contact_label = billing_contact_label or ""

    context.contact_email = (
        doc.contact_email
        or client_defaults.get("contact_email")
        or resolved.get("contact_email")
        or ""
    )

    context.price_list = (
        doc.selling_price_list
        or client_defaults.get("price_list")
        or resolved.get("price_list")
        or ""
    )

    context.company_label = (
        doc.company
        or client_defaults.get("company")
        or resolved.get("company")
        or ""
    )

    context.coach_label = (
        client_defaults.get("coach_label")
        or resolved.get("coach_label")
        or ""
    )

    context.bank_display_text = (
        client_defaults.get("bank_display_text")
        or resolved.get("bank_display_text")
        or ""
    )

    context.initial_client_defaults_json = json.dumps(client_defaults or {})

    context.initial_items_json = json.dumps([
        {
            "item_code": row.item_code or "",
            "description": row.description or "",
            "qty": row.qty or 1,
            "rate": row.rate or 0,
            "amount": row.amount or 0,
        }
        for row in (doc.items or [])
    ])
