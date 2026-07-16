import frappe
from frappe import _
from frappe.utils import get_fullname

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("session_worker")

    context.no_cache = 1
    context.page_title = "Reports"
    context.active_page = "reports"
    context.dashboard_base_url = "/session_worker_db"
    context.dashboard_user_name = get_fullname(frappe.session.user)
