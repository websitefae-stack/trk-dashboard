import frappe
from frappe import _
from frappe.utils import get_fullname


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    context.no_cache = 1
    context.active_page = "calendar"
    context.dashboard_type = "franchisor"
    context.dashboard_notifications_url = "/franchisor_db/notifications"
    context.dashboard_user_name = get_fullname(frappe.session.user)
