import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.profile import (
    get_profile_context,
    get_profile_display_name,
)


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("coach")

    profile_context = get_profile_context("coach")

    coach = profile_context["profile_doc"]

    context.no_cache = 1
    context.page_title = "My Profile"
    context.active_page = "profile"

    context.profile_role = "coach"

    context.coach = coach
    context.profile_doc = coach
    context.user_doc = profile_context["user_doc"]

    context.dashboard_user_name = get_profile_display_name("coach")
    context.dashboard_notifications_url = "/coach_db/notifications"

    context.bank_account = profile_context["bank_account"]

    context.dbs_rows = profile_context["dbs_rows"]
    context.dbs_update_service_rows = profile_context["dbs_update_service_rows"]
    context.insurance_rows = profile_context["insurance_rows"]
    context.indemnity_rows = profile_context["indemnity_rows"]
