import frappe
from frappe import _

from dashboard.api.shared.directory import get_user_display_name
from dashboard.api.shared.notifications import (
    ensure_notification_access,
    ensure_notification_access_for_user,
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
    context.page_title = "Notification Details"
    context.active_page = "notifications"
    context.dashboard_notifications_url = "/session_worker_db/notifications"
    context.base_url = "/session_worker_db"
    context.dashboard_base_url = "/session_worker_db"

    context.session_worker_view_mode = view_mode
    context.session_worker_view_query = view_mode.get("query_string") or ""
    context.session_worker_is_view_mode = view_mode.get("is_view_mode") or 0
    context.session_worker_view_return_to = view_mode.get("return_to") or ""
    context.session_worker_view_display_name = view_mode.get("view_worker_display_name") or ""

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

    docname = frappe.form_dict.get("name")

    if not docname:
        frappe.throw(_("Notification not found."))

    if context.session_worker_is_view_mode:
        view_worker_name = view_mode.get("view_worker_name")
        view_user = get_session_worker_user(view_worker_name)

        if not view_user:
            frappe.throw(_("Session worker user not found."), frappe.PermissionError)

        notification = ensure_notification_access_for_user(
            docname,
            view_user,
        )
    else:
        notification = ensure_notification_access(docname)

    context.notification = notification.as_dict()
    context.notification_docname = notification.name


def get_session_worker_user(worker_name):
    worker_name = (worker_name or "").strip()

    if not worker_name:
        return ""

    if not frappe.db.exists("Session Worker", worker_name):
        return ""

    meta = frappe.get_meta("Session Worker")

    for fieldname in [
        "user",
        "user_id",
        "email",
        "session_worker_email",
        "sw_email",
    ]:
        if meta.has_field(fieldname):
            value = frappe.db.get_value(
                "Session Worker",
                worker_name,
                fieldname,
            )

            if value:
                return value

    return ""
