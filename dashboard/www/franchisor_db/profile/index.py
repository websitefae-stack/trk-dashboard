import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    context.no_cache = 1
    context.page_title = "Franchisor Profile"
    context.active_page = "profile"
    context.dashboard_user_name = frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user
    context.dashboard_notifications_url = "/franchisor_db/notifications"
