import frappe
from frappe import _
from dashboard.api.shared.clients import normalize_client_row
from trk_session_worker_dashboard.api.clients import (
    _get_allowed_client_names,
    get_session_worker_display_name,
)


@frappe.whitelist()
def get_clients():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    allowed_names = _get_allowed_client_names()

    if not allowed_names:
        return []

    clients = frappe.get_all(
        "Client",
        filters={"name": ["in", allowed_names]},
        fields=[
            "name",
            "name1",
            "last_name",
            "full_name",
            "preferred_name",
            "mobile",
            "email",
            "status",
            "client_type",
            "primary_coach",
            "session_worker",
        ],
        order_by="full_name asc",
        limit_page_length=500,
    )

    return [normalize_client_row(c) for c in clients]


@frappe.whitelist()
def get_session_worker_name():
    return get_session_worker_display_name()
