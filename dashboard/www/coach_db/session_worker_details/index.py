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

    worker_name = frappe.form_dict.get("name")

    if not worker_name:
        frappe.throw(_("Session Worker not found."))

    context.no_cache = 1
    context.page_title = "Session Worker Details"
    context.active_page = "session_workers"
    context.dashboard_notifications_url = "/coach_db/notifications"

    context.coach_view_mode = view_mode
    context.coach_view_query = view_mode.get("query_string") or ""
    context.coach_is_view_mode = view_mode.get("is_view_mode") or 0
    context.coach_view_return_to = view_mode.get("return_to") or ""
    context.coach_view_display_name = view_mode.get("view_coach_display_name") or ""

    if context.coach_is_view_mode:
        context.dashboard_user_name = context.coach_view_display_name
        scope = "franchisor"
    else:
        redirect_if_wrong_dashboard("coach")
        context.dashboard_user_name = get_coach_display_name()
        scope = "coach"

    data = get_session_workers(scope=scope)
    workers = data.get("session_workers") or []

    selected_worker = None

    for worker in workers:
        if worker.get("name") == worker_name:
            selected_worker = worker
            break

    if not selected_worker:
        frappe.throw(
            _("You do not have permission to view this session worker."),
            frappe.PermissionError,
        )

    context.session_worker = selected_worker
    context.linked_clients = selected_worker.get("linked_clients") or []

    context.back_url = (
        "/coach_db/session_workers"
        + (context.coach_view_query or "")
    )

        return_to = (
        "/coach_db/session_worker_details?name="
        + frappe.utils.quote(worker_name)
        + (context.coach_view_query.replace("?", "&") if context.coach_view_query else "")
    )

    context.session_worker_dashboard_url = (
        "/session_worker_db"
        + "?view_as="
        + frappe.utils.quote(worker_name)
        + "&viewer=coach"
        + "&return_to="
        + frappe.utils.quote(return_to)
    )

    context.client_details_base_url = "/coach_db/client_details"
