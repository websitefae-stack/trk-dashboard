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

    context.no_cache = 1
    context.page_title = "Onboarding"
    context.active_page = "onboarding"
    context.dashboard_user_name = get_franchisor_display_name()
