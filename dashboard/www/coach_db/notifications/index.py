import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.directory import get_coach_display_name
from dashboard.api.shared.notifications import (
    get_notification_list_for_page,
    get_notification_summary_for_page,
)
from dashboard.api.shared.coach_view_mode import get_coach_view_mode


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    view_as = frappe.form_dict.get("view_as")
    viewer = frappe.form_dict.get("viewer")

    view_mode = get_coach_view_mode(
        scope=viewer,
        coach_name=view_as,
    )

    context.no_cache = 1
    context.page_title = "Notifications"
    context.active_page = "notifications"
    context.dashboard_notifications_url = "/coach_db/notifications"
    context.base_url = "/coach_db"

    context.coach_view_mode = view_mode
    context.coach_view_query = view_mode.get("query_string") or ""
    context.coach_is_view_mode = view_mode.get("is_view_mode") or 0
    context.coach_view_return_to = view_mode.get("return_to") or ""
    context.coach_view_display_name = view_mode.get("view_coach_display_name") or ""

    context.notifications = []
    context.unread_count = 0
    context.page_error = ""

    if context.coach_is_view_mode:
        context.dashboard_user_name = context.coach_view_display_name
    else:
        redirect_if_wrong_dashboard("coach")

        try:
            context.dashboard_user_name = get_coach_display_name()
        except Exception:
            context.dashboard_user_name = (
                frappe.get_cached_value(
                    "User",
                    frappe.session.user,
                    "full_name",
                )
                or ""
            )

    try:
        summary = get_notification_summary_for_page(limit=5)

        context.unread_count = summary.get("unread_count", 0)

        context.notifications = get_notification_list_for_page(
            status="All",
            limit=200,
        )

    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Coach Notifications Page Error",
        )

        context.notifications = []
        context.unread_count = 0
        context.page_error = _("Unable to load notifications.")
