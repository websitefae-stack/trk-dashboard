import frappe
from frappe import _
from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.franchisor.clients import (
    get_clients,
    get_client_types,
    get_coaches,
    get_franchisor_display_name,
    get_session_workers,
    get_my_coach_name,
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

    context.client_scope = frappe.form_dict.get("scope") or "my"
    context.my_coach_name = get_my_coach_name()
    context.my_coach_display_name = frappe.db.get_value(
        "Coach",
        context.my_coach_name,
        "coach_name",
    ) or "My clients"
    context.clients = get_clients(scope=context.client_scope)
    context.client_types = get_client_types()
    context.session_workers = get_session_workers()
    context.coaches = get_coaches()
