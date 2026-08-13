import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard, get_current_coach_name


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("coach")

    context.no_cache = 1
    context.page_title = "Onboarding"
    context.active_page = "onboarding"
    context.dashboard_notifications_url = "/coach_db/notifications"

    context.dashboard_user_name = frappe.db.get_value(
        "Coach",
        get_current_coach_name(),
        "coach_name",
    ) or frappe.session.user
