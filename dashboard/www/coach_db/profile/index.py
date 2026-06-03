import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.profile import (
    get_profile_context,
    get_profile_display_name,
)
from dashboard.api.shared.coach_view_mode import get_coach_view_mode


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    view_as = frappe.form_dict.get("view_as")
    viewer = frappe.form_dict.get("viewer")

    view_mode = get_coach_view_mode(
        scope=viewer,
        coach_name=view_as,
    )

    context.no_cache = 1
    context.page_title = "My Profile"
    context.active_page = "profile"
    context.profile_role = "coach"
    context.dashboard_notifications_url = "/coach_db/notifications"
    context.dashboard_base_url = "/coach_db"

    context.coach_view_mode = view_mode
    context.coach_view_query = view_mode.get("query_string") or ""
    context.coach_is_view_mode = view_mode.get("is_view_mode") or 0
    context.coach_view_return_to = view_mode.get("return_to") or ""
    context.coach_view_display_name = view_mode.get("view_coach_display_name") or ""

    if context.coach_is_view_mode:
        coach = frappe.get_doc("Coach", view_mode.get("view_coach_name"))

        user_email = coach.get("user") or coach.get("coach_email") or frappe.session.user
        user_doc = frappe.get_doc("User", user_email) if frappe.db.exists("User", user_email) else frappe.get_doc("User", frappe.session.user)

        bank_account = None
        if coach.get("bank_account"):
            bank_account = frappe.get_doc("Bank Account", coach.get("bank_account"))

        context.dashboard_user_name = context.coach_view_display_name
        context.coach = coach
        context.profile_doc = coach
        context.user_doc = user_doc
        context.bank_account = bank_account

        context.can_request_banking_change = 0
        context.can_edit_banking_directly = 0

        context.dbs_rows = coach.get("dbs") or []
        context.dbs_update_service_rows = coach.get("dbs_update_services") or []
        context.insurance_rows = coach.get("insurance") or []
        context.indemnity_rows = coach.get("indemnity") or []

    else:
        redirect_if_wrong_dashboard("coach")

        profile_context = get_profile_context("coach")
        coach = profile_context["profile_doc"]

        context.dashboard_user_name = get_profile_display_name("coach")
        context.coach = coach
        context.profile_doc = coach
        context.user_doc = profile_context["user_doc"]
        context.bank_account = profile_context["bank_account"]

        context.can_request_banking_change = profile_context["can_request_banking_change"]
        context.can_edit_banking_directly = profile_context["can_edit_banking_directly"]

        context.dbs_rows = profile_context["dbs_rows"]
        context.dbs_update_service_rows = profile_context["dbs_update_service_rows"]
        context.insurance_rows = profile_context["insurance_rows"]
        context.indemnity_rows = profile_context["indemnity_rows"]
