import frappe
from frappe import _
from dashboard.api.franchisor.clients import (
    get_clients,
    get_coaches,
    get_franchisor_display_name,
    get_session_workers,
)
from dashboard.api.shared.clients import get_client_types


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    context.no_cache = 1
    context.page_title = "Clients"
    context.active_page = "clients"

    context.dashboard_user_name = get_franchisor_display_name()
    context.dashboard_notifications_url = "/franchisor_db/notifications"

    context.clients = get_clients(scope="my")
    context.client_types = get_client_types()
    context.coaches = get_coaches()
    context.session_workers = get_session_workers()

    context.client_detail_base_url = "/franchisor_db/client_details"
    context.add_client_url = "/franchisor_db/client_details"
