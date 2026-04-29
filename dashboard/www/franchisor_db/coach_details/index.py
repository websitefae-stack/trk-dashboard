import frappe
from frappe import _

from dashboard.api.franchisor.clients import get_franchisor_display_name
from dashboard.api.shared.permissions import ensure_franchisor_can_access_coach


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    coach_name = frappe.form_dict.get("name")
    if not coach_name:
        frappe.throw(_("Coach not found."))

    coach = ensure_franchisor_can_access_coach(coach_name)

    context.no_cache = 1
    context.page_title = "Coach Details"
    context.active_page = "coaches"

    context.dashboard_user_name = get_franchisor_display_name()
    context.dashboard_notifications_url = "/franchisor_db/notifications"

    context.coach = coach
