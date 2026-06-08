import frappe
from frappe import _

from dashboard.api.shared.directory import get_user_display_name
from dashboard.api.shared.notifications import (
    get_notification_list_for_page,
    get_notification_summary_for_page,
    get_notification_list_for_session_worker_doc,
    get_notification_summary_for_session_worker_doc,
)
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
    context.page_title = "Notifications"
    context.active_page = "notifications"
    context.dashboard_notifications_url = "/session_worker_db/notifications" + (view_mode.get("query_string") or "")
    context.base_url = "/session_worker_db"
    context.dashboard_base_url = "/session_worker_db"

    context.session_worker_view_mode = view_mode
    context.session_worker_view_query = view_mode.get("query_string") or ""
    context.session_worker_is_view_mode = view_mode.get("is_view_mode") or 0
    context.session_worker_view_return_to = view_mode.get("return_to") or ""
    context.session_worker_view_display_name = view_mode.get("view_worker_display_name") or ""

    context.notifications = []
    context.unread_count = 0
    context.page_error = ""

    if context.session_worker_is_view_mode:
        context.dashboard_user_name = context.session_worker_view_display_name
    else:
        try:
            context.dashboard_user_name = get_user_display_name()
        except Exception:
            context.dashboard_user_name = frappe.get_cached_value(
                "User",
                frappe.session.user,
                "full_name",
            ) or ""

    try:
        if context.session_worker_is_view_mode:
            worker_name = view_mode.get("view_worker_name")

            summary = get_notification_summary_for_session_worker_doc(
                worker_name,
                limit=5,
            )

            context.unread_count = summary.get("unread_count", 0)

            context.notifications = get_notification_list_for_session_worker_doc(
                worker_name,
                status="All",
                limit=200,
            )

        else:
            summary = get_notification_summary_for_page(limit=5)
            context.unread_count = summary.get("unread_count", 0)

            context.notifications = get_notification_list_for_page(
                status="All",
                limit=200,
            )

    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Session Worker Notifications Page Error",
        )

        context.notifications = []
        context.unread_count = 0
        context.page_error = _("Unable to load notifications.")
