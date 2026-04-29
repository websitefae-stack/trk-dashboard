import frappe
from frappe import _
from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.session_worker.client_details import (
    get_client_for_context,
    get_session_worker_name,
)


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("session_worker")

    context.no_cache = 1
    context.page_title = "Client Details"
    context.active_page = "clients"
    context.dashboard_notifications_url = "/session_worker_db/notifications"
    context.dashboard_user_name = get_session_worker_name()

    client_name = frappe.form_dict.get("name")
    if not client_name:
        frappe.throw(_("Client not found."))

    client = get_client_for_context(client_name)

    context.client = client.as_dict()
    context.client_docname = client.name
    context.client_title = client.get("full_name") or client.name
