import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard, get_current_session_worker_name


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("session_worker")

    context.no_cache = 1
    context.page_title = "Onboarding"
    context.active_page = "onboarding"
    context.dashboard_notifications_url = "/session_worker_db/notifications"

    context.dashboard_user_name = frappe.db.get_value(
        "Session Worker",
        get_current_session_worker_name(),
        "sw_name",
    ) or frappe.session.user
