import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.directory import get_franchisor_display_name
from dashboard.api.shared.session_workers import get_session_workers


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    context.no_cache = 1
    context.page_title = "Session Workers"
    context.active_page = "session_workers"
    context.dashboard_notifications_url = "/franchisor_db/notifications"
    context.dashboard_user_name = get_franchisor_display_name()

    data = get_session_workers(scope="franchisor")

    context.session_worker_context = data
    context.session_workers = data.get("session_workers") or []

    coach_options = {}

    for worker in context.session_workers:
        for coach in worker.get("linked_coaches") or []:
            if coach.get("name"):
                coach_options[coach.get("name")] = coach.get("display_name") or coach.get("name")

    context.coach_filter_options = [
        {"name": name, "display_name": label}
        for name, label in sorted(coach_options.items(), key=lambda item: item[1].lower())
    ]
