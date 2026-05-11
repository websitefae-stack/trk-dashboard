import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.directory import get_coach_display_name
from dashboard.api.shared.session_workers import get_session_workers


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("coach")

    context.no_cache = 1
    context.page_title = "Session Workers"
    context.active_page = "session_workers"
    context.dashboard_notifications_url = "/coach_db/notifications"
    context.dashboard_user_name = get_coach_display_name()

    data = get_session_workers(scope="coach")

    context.session_worker_context = data
    context.session_workers = data.get("session_workers") or []
    context.current_coach = data.get("current_coach") or ""
    context.current_coach_label = data.get("current_coach_label") or ""
