import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.franchisor.clients import get_franchisor_display_name
from dashboard.api.shared.notifications import (
    get_notification_list_for_page,
    get_notification_summary_for_page,
)


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    context.no_cache = 1
    context.page_title = "Notifications"
    context.active_page = "notifications"
    context.dashboard_notifications_url = "/franchisor_db/notifications"
    context.dashboard_base_url = "/franchisor_db"

    context.notifications = []
    context.unread_count = 0
    context.page_error = ""

    try:
        context.dashboard_user_name = get_franchisor_display_name()
    except Exception:
        context.dashboard_user_name = frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user

    try:
        summary = get_notification_summary_for_page(limit=5)
        context.unread_count = summary.get("unread_count", 0)
        context.notifications = get_notification_list_for_page(status="All", limit=100)

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Franchisor Notifications Page Error")
        context.notifications = []
        context.unread_count = 0
        context.page_error = _("Unable to load notifications.")
