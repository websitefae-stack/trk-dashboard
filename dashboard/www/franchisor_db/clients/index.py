import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.clients import get_paginated_clients, get_client_types
from dashboard.api.shared.directory import (
    get_franchisor_display_name,
    get_session_workers,
    get_coaches,
)


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    context.no_cache = 1
    context.page_title = "Clients"
    context.active_page = "clients"
    context.dashboard_notifications_url = "/franchisor_db/notifications"
    context.dashboard_user_name = get_franchisor_display_name()

    client_data = get_paginated_clients()

    context.clients = client_data.get("clients", [])
    context.pagination = client_data.get("pagination", {})
    context.search = client_data.get("search", "")
    context.client_types = get_client_types()
    context.session_workers = get_session_workers()
    context.coaches = get_coaches()
