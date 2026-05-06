import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.contacts import get_contacts_for_scope


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("session_worker")

    context.no_cache = 1
    context.page_title = "Contacts"
    context.active_page = "contacts"

    context.dashboard_user_name = frappe.db.get_value(
        "Session Worker",
        {"user": frappe.session.user},
        "sw_name",
    ) or frappe.session.user

    context.contacts = get_contacts_for_scope("session_worker")
