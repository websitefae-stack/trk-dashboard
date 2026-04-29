import frappe
from frappe import _


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    context.no_cache = 1
    context.page_title = "Session Worker Dashboard"
    context.active_page = "dashboard"
    context.dashboard_notifications_url = "/session_worker_db/notifications"
    context.dashboard_user_name = frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user
