import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.coach.profile import get_coach_display_name
from dashboard.api.coach.session_workers import get_linked_session_workers


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("coach")

    context.no_cache = 1
    context.page_title = "Session Workers"
    context.active_page = "session_workers"

    context.dashboard_user_name = get_coach_display_name()
    context.dashboard_notifications_url = "/coach_db/notifications"

    context.session_workers = get_linked_session_workers()
    context.session_worker_detail_base_url = "/coach_db/session_worker_details"
