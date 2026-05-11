import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.directory import get_franchisor_display_name
from dashboard.api.shared.coaches import get_coaches


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    context.no_cache = 1
    context.page_title = "Coaches"
    context.active_page = "coaches"
    context.dashboard_notifications_url = "/franchisor_db/notifications"
    context.dashboard_user_name = get_franchisor_display_name()

    context.coaches = get_coaches()
