import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.directory import get_franchisor_display_name

OFFICE_USER = "office@theresilienthub.co.uk"


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    if frappe.session.user != OFFICE_USER:
        frappe.throw(_("You do not have permission to view this page."), frappe.PermissionError)

    context.no_cache = 1
    context.page_title = "Reports"
    context.active_page = "reports"
    context.dashboard_base_url = "/franchisor_db"

    try:
        context.dashboard_user_name = get_franchisor_display_name()
    except Exception:
        context.dashboard_user_name = frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user
