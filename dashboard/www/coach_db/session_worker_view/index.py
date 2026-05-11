import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.directory import get_coach_display_name
from dashboard.api.shared.session_workers import get_session_workers
from dashboard.api.shared.session_worker_view import get_session_worker_dashboard_summary


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("coach")

    worker_name = frappe.form_dict.get("name")

    if not worker_name:
        frappe.throw(_("Session Worker not found."))

    data = get_session_workers(scope="coach")
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

    dashboard_summary = get_session_worker_dashboard_summary(
        scope="coach",
        worker_name=worker_name,
    )

    context.no_cache = 1
    context.page_title = "Viewing Session Worker"
    context.active_page = "session_workers"
    context.dashboard_notifications_url = "/coach_db/notifications"
    context.dashboard_user_name = get_coach_display_name()

    context.view_scope = "coach"
    context.session_worker = selected_worker
    context.session_worker_name = selected_worker.get("name")
    context.session_worker_display_name = selected_worker.get("display_name") or selected_worker.get("name")
    context.back_url = "/coach_db/session_workers"

    context.dashboard_summary = dashboard_summary
