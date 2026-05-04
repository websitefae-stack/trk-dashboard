import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.contact_details import get_contact_context
from dashboard.api.franchisor.clients import get_franchisor_display_name


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    is_new = bool(frappe.form_dict.get("new"))

    data = get_contact_context(
        scope="franchisor",
        contact_name=frappe.form_dict.get("name"),
        is_new=is_new,
    )

    context.no_cache = 1
    context.page_title = data["contact_display_name"]
    context.active_page = "contacts"
    context.dashboard_user_name = get_franchisor_display_name()
    context.dashboard_notifications_url = "/franchisor_db/notifications"

    for key, value in data.items():
        context[key] = value
