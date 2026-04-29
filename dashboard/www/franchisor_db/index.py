import frappe
from frappe import _
from dashboard.api.franchisor.clients import get_franchisor_display_name


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    context.no_cache = 1
    context.page_title = "Franchisor Dashboard"
    context.active_page = "dashboard"
    context.dashboard_notifications_url = "/franchisor_db/notifications"

    try:
        context.dashboard_user_name = get_franchisor_display_name()
    except Exception:
        context.dashboard_user_name = frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user
