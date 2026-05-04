import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.coach.profile import get_coach_doc, get_coach_display_name


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    coach = get_coach_doc()  # franchisor uses Coach doctype

    context.no_cache = 1
    context.page_title = "Franchisor Profile"
    context.active_page = "profile"

    context.coach = coach
    context.dashboard_user_name = get_coach_display_name()
    context.dashboard_notifications_url = "/franchisor_db/notifications"

    context.bank_account = None
    if coach.bank_account:
        context.bank_account = frappe.get_doc("Bank Account", coach.bank_account)

    context.dbs_rows = coach.get("dbs") or []
    context.dbs_update_service_rows = coach.get("dbs_update_services") or []
    context.insurance_rows = coach.get("insurance") or []
    context.indemnity_rows = coach.get("indemnity") or []
