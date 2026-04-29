import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.contact_details import get_contact_context


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("session_worker")

    data = get_contact_context(
        scope="session_worker",
        contact_name=frappe.form_dict.get("name"),
        is_new=False,
    )

    context.no_cache = 1
    context.page_title = data["contact_display_name"]
    context.active_page = "contacts"
    context.dashboard_notifications_url = "/session_worker_db/notifications"

    for key, value in data.items():
        context[key] = value
