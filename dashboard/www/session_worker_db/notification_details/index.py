import frappe
from frappe import _

from dashboard.api.shared.directory import get_user_display_name
from dashboard.api.shared.notifications import ensure_notification_access
from dashboard.api.shared.session_worker_view_mode import get_session_worker_view_mode


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    view_as = frappe.form_dict.get("view_as")
    viewer = frappe.form_dict.get("viewer")

    view_mode = get_session_worker_view_mode(
        scope=viewer,
        worker_name=view_as,
    )

    context.no_cache = 1
    context.page_title = "Notification Details"
    context.active_page = "notifications"
    context.dashboard_notifications_url = "/session_worker_db/notifications"
    context.base_url = "/session_worker_db"

    context.session_worker_view_mode = view_mode
    context.session_worker_view_query = view_mode.get("query_string") or ""
    context.session_worker_is_view_mode = view_mode.get("is_view_mode") or 0
    context.session_worker_view_return_to = view_mode.get("return_to") or ""
    context.session_worker_view_display_name = view_mode.get("view_worker_display_name") or ""

    if context.session_worker_is_view_mode:
        context.dashboard_user_name = context.session_worker_view_display_name
        frappe.throw(
            _("Notification detail read-only view will be connected after the notifications API is updated."),
            frappe.PermissionError,
        )
    else:
        try:
            context.dashboard_user_name = get_user_display_name()
        except Exception:
            context.dashboard_user_name = frappe.get_cached_value("User", frappe.session.user, "full_name") or ""

    docname = frappe.form_dict.get("name")

    if not docname:
        frappe.throw(_("Notification not found."))

    notification = ensure_notification_access(docname)

    context.notification = notification.as_dict()
    context.notification_docname = notification.name
