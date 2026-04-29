import frappe
from frappe import _
from dashboard.api.coach.profile import get_coach_doc, get_coach_display_name


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    coach = get_coach_doc()

    context.coach = coach
    context.dashboard_user_name = get_coach_display_name()
    context.dashboard_notifications_url = "/coach_db/notifications"

    # bank account
    context.bank_account = None
    if coach.bank_account:
        context.bank_account = frappe.get_doc("Bank Account", coach.bank_account)
