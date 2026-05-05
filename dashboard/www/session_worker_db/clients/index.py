import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.clients import get_clients, get_client_types
from dashboard.api.session_worker.client_details import get_session_worker_name


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("session_worker")

    context.no_cache = 1
    context.page_title = "Clients"
    context.active_page = "clients"
    context.dashboard_notifications_url = "/session_worker_db/notifications"
    context.dashboard_user_name = get_session_worker_name()

    context.clients = get_clients()
    context.client_types = get_client_types()
