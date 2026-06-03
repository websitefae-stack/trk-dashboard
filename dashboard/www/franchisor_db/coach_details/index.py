import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard


def get_franchisor_display_name():
    return (
        frappe.db.get_value(
            "Coach",
            {"user": frappe.session.user},
            "coach_name",
        )
        or frappe.session.user
    )


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    coach_name = frappe.form_dict.get("name")

    if not coach_name:
        frappe.throw(_("Coach not found."))

    if not frappe.db.exists("Coach", coach_name):
        frappe.throw(_("Coach not found."))

    coach = frappe.get_doc("Coach", coach_name)

    context.no_cache = 1
    context.page_title = coach.coach_name or coach.name
    context.active_page = "coaches"
    context.dashboard_user_name = get_franchisor_display_name()
    context.dashboard_notifications_url = "/franchisor_db/notifications"

    context.coach = coach
