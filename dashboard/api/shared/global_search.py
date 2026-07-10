"""
Topbar "search everything" box - type a client's name and jump straight to
their file, or type an invoice amount and jump to the invoice list filtered
to that amount. Scoped to whatever the logged-in user is already allowed to
see (same rules as the Clients/Invoices list pages).
"""

import frappe

from dashboard.api.shared.permissions import (
    ensure_logged_in,
    is_franchisor_user,
    get_current_user_dashboard_type,
    get_allowed_client_names,
)
from dashboard.api.shared.clients import build_display_name

MAX_RESULTS_PER_GROUP = 6


def _base_url():
    dashboard_type = get_current_user_dashboard_type()
    if dashboard_type == "franchisor":
        return "/franchisor_db"
    if dashboard_type == "session_worker":
        return "/session_worker_db"
    return "/coach_db"


def _parse_amount(query):
    cleaned = query.replace("£", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _search_clients(query, allowed_names, base_url):
    filters = {}
    if allowed_names is not None:
        if not allowed_names:
            return []
        filters["name"] = ["in", allowed_names]

    or_filters = [
        ["name1", "like", f"%{query}%"],
        ["last_name", "like", f"%{query}%"],
        ["full_name", "like", f"%{query}%"],
        ["preferred_name", "like", f"%{query}%"],
        ["email", "like", f"%{query}%"],
        ["mobile", "like", f"%{query}%"],
    ]

    meta = frappe.get_meta("Client")
    fields = ["name"]
    for fieldname in ["name1", "last_name", "full_name", "preferred_name", "email"]:
        if meta.has_field(fieldname):
            fields.append(fieldname)

    or_filters = [f for f in or_filters if meta.has_field(f[0])]
    if not or_filters:
        return []

    rows = frappe.get_all(
        "Client",
        filters=filters,
        or_filters=or_filters,
        fields=fields,
        limit_page_length=MAX_RESULTS_PER_GROUP,
        ignore_permissions=True,
    )

    results = []
    for row in rows:
        subtitle = row.get("email") or ""
        results.append({
            "type": "client",
            "title": build_display_name(row),
            "subtitle": subtitle,
            "url": f"{base_url}/client_details?name={row.get('name')}",
        })

    return results


def _search_invoices(query, allowed_names, base_url):
    filters = {"docstatus": ["!=", 2]}
    if allowed_names is not None:
        if not allowed_names:
            return []
        filters["custom_client"] = ["in", allowed_names]

    or_filters = [["name", "like", f"%{query}%"]]

    amount_value = _parse_amount(query)
    if amount_value is not None:
        or_filters.append(["grand_total", "between", [amount_value - 0.005, amount_value + 0.005]])

    rows = frappe.get_all(
        "Sales Invoice",
        filters=filters,
        or_filters=or_filters,
        fields=["name", "custom_client", "customer_name", "grand_total", "currency"],
        order_by="posting_date desc",
        limit_page_length=MAX_RESULTS_PER_GROUP,
        ignore_permissions=True,
    )

    client_cache = {}

    def client_label(client_name):
        if not client_name:
            return None
        if client_name not in client_cache:
            row = frappe.db.get_value(
                "Client", client_name, ["name1", "last_name", "full_name", "preferred_name"], as_dict=True
            )
            client_cache[client_name] = build_display_name(row) if row else None
        return client_cache[client_name]

    results = []
    for row in rows:
        amount = row.get("grand_total") or 0
        currency = row.get("currency") or "GBP"
        subtitle = client_label(row.get("custom_client")) or row.get("customer_name") or ""

        results.append({
            "type": "invoice",
            "title": f"{row.get('name')} — {currency} {amount:,.2f}",
            "subtitle": subtitle,
            "url": f"{base_url}/invoice_details?name={row.get('name')}",
        })

    if amount_value is not None and len(rows) >= MAX_RESULTS_PER_GROUP:
        results.append({
            "type": "invoice-list",
            "title": f"See all invoices totalling {amount_value:,.2f}",
            "subtitle": "",
            "url": f"{base_url}/invoices?search={query}",
        })

    return results


@frappe.whitelist()
def search(query=None):
    ensure_logged_in()

    query = (query or "").strip()
    if len(query) < 2:
        return {"results": []}

    allowed_names = None if is_franchisor_user() else get_allowed_client_names()
    base_url = _base_url()
    dashboard_type = get_current_user_dashboard_type()

    results = []
    results.extend(_search_clients(query, allowed_names, base_url))

    # Session workers don't have an invoices area of the dashboard at all.
    if dashboard_type != "session_worker":
        results.extend(_search_invoices(query, allowed_names, base_url))

    return {"results": results}
