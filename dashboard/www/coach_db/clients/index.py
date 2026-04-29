import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.coach.clients import (
    get_clients,
    get_coach_display_name,
    get_session_workers,
)
from dashboard.api.shared.clients import get_client_types


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("coach")

    context.no_cache = 1
    context.page_title = "Clients"
    context.active_page = "clients"

    context.dashboard_user_name = get_coach_display_name()
    context.dashboard_notifications_url = "/coach_db/notifications"

    context.clients = get_clients()
    context.client_types = get_client_types()
    context.session_workers = get_session_workers()

    context.client_detail_base_url = "/coach_db/client_details"
    context.add_client_url = "/coach_db/client_details"
