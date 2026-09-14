import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.directory import get_franchisor_display_name


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    context.no_cache = 1
    context.page_title = "School Details"
    context.active_page = "schools"
    context.dashboard_user_name = get_franchisor_display_name()
    context.school_name_param = frappe.form_dict.get("name") or ""
