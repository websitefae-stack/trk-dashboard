import frappe
from frappe import _

from dashboard.api.shared.clients import get_clients, get_client_types
from dashboard.api.shared.session_worker_view_mode import (
    get_session_worker_view_mode,
    get_clients_for_view_session_worker,
)


def get_session_worker_display_name():
    return (
        frappe.db.get_value(
            "Session Worker",
            {"user": frappe.session.user},
            "sw_name",
        )
        or frappe.db.get_value(
            "Session Worker",
            {"sw_email": frappe.session.user},
            "sw_name",
        )
        or frappe.get_cached_value("User", frappe.session.user, "full_name")
        or frappe.session.user
    )


def get_current_coach_name():
    if not frappe.db.exists("DocType", "Coach"):
        return ""

    meta = frappe.get_meta("Coach")

    for fieldname in ["user", "user_id", "email", "coach_email"]:
        if meta.has_field(fieldname):
            coach = frappe.db.get_value(
                "Coach",
                {fieldname: frappe.session.user},
                "name",
            )

            if coach:
                return coach

    return ""


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
    context.page_title = "Clients"
    context.active_page = "clients"
    context.dashboard_notifications_url = "/session_worker_db/notifications"

    context.session_worker_view_mode = view_mode
    context.session_worker_view_query = view_mode.get("query_string") or ""
    context.session_worker_is_view_mode = view_mode.get("is_view_mode") or 0
    context.session_worker_view_return_to = view_mode.get("return_to") or ""
    context.session_worker_view_display_name = view_mode.get("view_worker_display_name") or ""

    context.viewer_coach_name = get_current_coach_name()

    if context.session_worker_is_view_mode:
        context.dashboard_user_name = context.session_worker_view_display_name
        context.clients = get_clients_for_view_session_worker(view_mode.get("view_worker_name"))
    else:
        context.dashboard_user_name = get_session_worker_display_name()
        context.clients = get_clients()

    context.client_types = get_client_types()
