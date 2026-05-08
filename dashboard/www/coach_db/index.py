import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("coach")

    context.no_cache = 1
    context.page_title = "Coach Dashboard"
    context.active_page = "dashboard"
    context.dashboard_user_name = frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user
