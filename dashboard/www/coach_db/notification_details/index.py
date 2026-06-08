import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.directory import get_coach_display_name
from dashboard.api.shared.notifications import (
    ensure_notification_access,
    ensure_notification_access_for_user,
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
    context.page_title = "Notification Details"
    context.active_page = "notifications"
    context.dashboard_notifications_url = "/coach_db/notifications" + (view_mode.get("query_string") or "")
    context.dashboard_base_url = "/coach_db"
    context.base_url = "/coach_db"

    context.coach_view_mode = view_mode
    context.coach_view_query = view_mode.get("query_string") or ""
    context.coach_is_view_mode = view_mode.get("is_view_mode") or 0
    context.coach_view_return_to = view_mode.get("return_to") or ""
    context.coach_view_display_name = view_mode.get("view_coach_display_name") or ""

    if context.coach_is_view_mode:
        context.dashboard_user_name = context.coach_view_display_name
    else:
        redirect_if_wrong_dashboard("coach")

        try:
            context.dashboard_user_name = get_coach_display_name()
        except Exception:
            context.dashboard_user_name = frappe.get_cached_value("User", frappe.session.user, "full_name") or ""

    docname = frappe.form_dict.get("name")
    if not docname:
        frappe.throw(_("Notification not found."))

    if context.coach_is_view_mode:
        coach_user = get_coach_user_from_docname(view_mode.get("view_coach_name"))

        if not coach_user:
            frappe.throw(_("Coach user not found."), frappe.PermissionError)

        notification = ensure_notification_access_for_user(docname, coach_user)
    else:
        notification = ensure_notification_access(docname)

    context.notification = notification.as_dict()
    context.notification_docname = notification.name


def get_coach_user_from_docname(coach_name):
    if not coach_name or not frappe.db.exists("Coach", coach_name):
        return ""

    meta = frappe.get_meta("Coach")

    for fieldname in ["user", "user_id", "email", "coach_email"]:
        if meta.has_field(fieldname):
            value = frappe.db.get_value("Coach", coach_name, fieldname)
            if value:
                return value

    return ""
