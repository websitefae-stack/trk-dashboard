import frappe
from frappe import _

from dashboard.api.coach.profile import get_coach_display_name
from dashboard.api.shared.permissions import ensure_coach_can_access_session_worker


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    session_worker_name = frappe.form_dict.get("name")
    if not session_worker_name:
        frappe.throw(_("Session Worker not found."))

    session_worker = ensure_coach_can_access_session_worker(session_worker_name)

    context.no_cache = 1
    context.page_title = "Session Worker Details"
    context.active_page = "session_workers"

    context.dashboard_user_name = get_coach_display_name()
    context.dashboard_notifications_url = "/coach_db/notifications"

    context.session_worker = session_worker
