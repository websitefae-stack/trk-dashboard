import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.directory import get_coach_display_name
from dashboard.api.shared.session_workers import get_session_workers
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
    context.page_title = "Session Workers"
    context.active_page = "session_workers"
    context.dashboard_notifications_url = "/coach_db/notifications"

    context.coach_view_mode = view_mode
    context.coach_view_query = view_mode.get("query_string") or ""
    context.coach_is_view_mode = view_mode.get("is_view_mode") or 0
    context.coach_view_return_to = view_mode.get("return_to") or ""
    context.coach_view_display_name = view_mode.get("view_coach_display_name") or ""

    if context.coach_is_view_mode:
        context.dashboard_user_name = context.coach_view_display_name
        context.session_workers = get_session_workers_for_view_coach(view_mode.get("view_coach_name"))
    else:
        redirect_if_wrong_dashboard("coach")
        context.dashboard_user_name = get_coach_display_name()
        data = get_session_workers(scope="coach")
        context.session_workers = data.get("session_workers") or []


def get_session_workers_for_view_coach(coach_name):
    if not coach_name:
        return []

    rows = frappe.get_all(
        "Session Worker",
        filters={"coach": coach_name},
        fields=[
            "name",
            "sw_name",
            "sw_email",
            "mobile",
            "phone",
            "status",
        ],
        order_by="sw_name asc",
        limit_page_length=5000,
        ignore_permissions=True,
    )

    return [
        {
            "name": row.name,
            "display_name": row.sw_name or row.name,
            "sw_name": row.sw_name,
            "sw_email": row.sw_email,
            "mobile": row.mobile or row.phone,
            "phone": row.phone,
            "status": row.status,
            "linked_clients": [],
        }
        for row in rows
    ]
