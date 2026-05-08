import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.directory import get_coach_display_name
from dashboard.api.shared.notifications import ensure_notification_access


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("coach")

    context.no_cache = 1
    context.page_title = "Notification Details"
    context.active_page = "notifications"
    context.dashboard_notifications_url = "/coach_db/notifications"
    context.base_url = "/coach_db"

    try:
        context.dashboard_user_name = get_coach_display_name()
    except Exception:
        context.dashboard_user_name = frappe.get_cached_value("User", frappe.session.user, "full_name") or ""

    docname = frappe.form_dict.get("name")
    if not docname:
        frappe.throw(_("Notification not found."))

    notification = ensure_notification_access(docname)

    context.notification = notification.as_dict()
    context.notification_docname = notification.name
