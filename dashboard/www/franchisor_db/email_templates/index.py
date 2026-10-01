import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.profile import OFFICE_USER


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    # Office-only, not Ashley's own login - ensure_office_user()/
    # is_franchisor_user() both treat Ashley and office as the same
    # tier (see FRANCHISOR_USERS in permissions.py), so this needs the
    # literal OFFICE_USER check instead, same pattern the Reports page
    # already uses for its own office-only diagnostics section. The nav
    # link itself matches this same check in franchisor_sidebar.html.
    if frappe.session.user != OFFICE_USER:
        frappe.throw(_("You are not allowed to access this page."), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    context.no_cache = 1
    context.page_title = "Email Templates"
    context.active_page = "email_templates"
    context.dashboard_base_url = "/franchisor_db"
    context.dashboard_type = "franchisor"
    context.current_user_email = frappe.session.user
