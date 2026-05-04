import frappe
from frappe import _


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    context.no_cache = 1
    context.active_page = "calendar"
    context.dashboard_notifications_url = "/session_worker_db/notifications"
