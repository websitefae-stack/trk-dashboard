import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    requirement_name = (frappe.form_dict.get("name") or "").strip()

    if not requirement_name:
        frappe.local.flags.redirect_location = "/franchisor_db/documents"
        raise frappe.Redirect

    context.no_cache = 1
    context.page_title = "Document"
    context.active_page = "documents"
    context.requirement_name = requirement_name
    context.dashboard_user_name = frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user
