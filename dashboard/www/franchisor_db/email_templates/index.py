import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    context.no_cache = 1
    context.page_title = "Email Templates"
    context.active_page = "email_templates"
    context.dashboard_base_url = "/franchisor_db"
    context.dashboard_type = "franchisor"
    context.current_user_email = frappe.session.user
