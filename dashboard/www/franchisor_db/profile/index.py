import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.profile import (
    get_profile_context,
    get_profile_display_name,
    get_franchisor_name,
    coach_has_secret_key,
)


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    profile_context = get_profile_context("franchisor")
    coach = profile_context["profile_doc"]

    context.no_cache = 1
    context.page_title = "My Profile"
    context.active_page = "profile"

    context.profile_role = "franchisor"

    context.coach = coach
    context.profile_doc = coach
    context.user_doc = profile_context["user_doc"]

    context.dashboard_user_name = (
        get_profile_display_name("franchisor")
        or get_franchisor_name()
    )
    context.dashboard_notifications_url = "/franchisor_db/notifications"
    context.dashboard_base_url = "/franchisor_db"

    context.bank_account = profile_context["bank_account"]
    context.can_request_banking_change = profile_context["can_request_banking_change"]
    context.can_edit_banking_directly = profile_context["can_edit_banking_directly"]

    context.dbs_rows = profile_context["dbs_rows"]
    context.dbs_update_service_rows = profile_context["dbs_update_service_rows"]
    context.insurance_rows = profile_context["insurance_rows"]
    context.indemnity_rows = profile_context["indemnity_rows"]

    context.has_secret_key = coach_has_secret_key(coach.name)
