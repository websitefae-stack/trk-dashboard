import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.franchisor.clients import get_franchisor_display_name
from dashboard.api.franchisor.notifications import ensure_notification_access


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    context.no_cache = 1
    context.page_title = "Notification Details"
    context.active_page = "notifications"
    context.dashboard_notifications_url = "/franchisor_db/notifications"

    try:
        context.dashboard_user_name = get_franchisor_display_name()
    except Exception:
        context.dashboard_user_name = frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user

    docname = frappe.form_dict.get("name")
    if not docname:
        frappe.throw(_("Notification not found."))

    notification = ensure_notification_access(docname)

    context.notification = notification.as_dict()
    context.notification_docname = notification.name
