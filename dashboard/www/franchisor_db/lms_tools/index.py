import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.profile import OFFICE_USER


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    # Office-only, not Ashley's own login - is_franchisor_user() treats
    # Ashley and office as the same tier (FRANCHISOR_USERS), so this
    # needs the literal OFFICE_USER check instead, same pattern Email
    # Templates already uses for its own office-only page. The nav link
    # itself matches this same check in franchisor_sidebar.html.
    if frappe.session.user != OFFICE_USER:
        frappe.throw(_("You are not allowed to access this page."), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    context.no_cache = 1
    context.page_title = "LMS Tools"
    context.active_page = "lms_tools"
    context.dashboard_user_name = frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user
