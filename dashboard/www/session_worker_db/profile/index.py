import frappe
from frappe import _

from dashboard.api.shared.profile import (
    get_profile_context,
    get_profile_display_name,
)
from dashboard.api.shared.session_worker_view_mode import get_session_worker_view_mode


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    view_as = frappe.form_dict.get("view_as")
    viewer = frappe.form_dict.get("viewer")

    view_mode = get_session_worker_view_mode(
        scope=viewer,
        worker_name=view_as,
    )

    context.no_cache = 1
    context.page_title = "My Profile"
    context.active_page = "profile"
    context.profile_role = "session_worker"
    context.dashboard_notifications_url = "/session_worker_db/notifications"
    context.dashboard_base_url = "/session_worker_db"

    context.session_worker_view_mode = view_mode
    context.session_worker_view_query = view_mode.get("query_string") or ""
    context.session_worker_is_view_mode = view_mode.get("is_view_mode") or 0
    context.session_worker_view_return_to = view_mode.get("return_to") or ""
    context.session_worker_view_display_name = view_mode.get("view_worker_display_name") or ""

    if context.session_worker_is_view_mode:
        session_worker = frappe.get_doc("Session Worker", view_mode.get("view_worker_name"))

        user_email = session_worker.get("user") or session_worker.get("sw_email") or frappe.session.user
        user_doc = frappe.get_doc("User", user_email) if frappe.db.exists("User", user_email) else frappe.get_doc("User", frappe.session.user)

        bank_account = None
        if session_worker.get("bank_account"):
            bank_account = frappe.get_doc("Bank Account", session_worker.get("bank_account"))

        context.dashboard_user_name = context.session_worker_view_display_name
        context.session_worker = session_worker
        context.profile_doc = session_worker
        context.user_doc = user_doc
        context.bank_account = bank_account

        context.can_request_banking_change = 0
        context.can_edit_banking_directly = 0

        context.dbs_rows = session_worker.get("dbs") or []
        context.dbs_update_service_rows = session_worker.get("dbs_update_service") or []
        context.insurance_rows = session_worker.get("insurance") or []
        context.indemnity_rows = session_worker.get("indemnity") or []

    else:
        profile_context = get_profile_context("session_worker")
        session_worker = profile_context["profile_doc"]

        context.dashboard_user_name = get_profile_display_name("session_worker")
        context.session_worker = session_worker
        context.profile_doc = session_worker
        context.user_doc = profile_context["user_doc"]
        context.bank_account = profile_context["bank_account"]

        context.can_request_banking_change = profile_context["can_request_banking_change"]
        context.can_edit_banking_directly = profile_context["can_edit_banking_directly"]

        context.dbs_rows = profile_context["dbs_rows"]
        context.dbs_update_service_rows = profile_context["dbs_update_service_rows"]
        context.insurance_rows = profile_context["insurance_rows"]
        context.indemnity_rows = profile_context["indemnity_rows"]

    context.linked_coaches = []

    if session_worker.meta.has_field("linked_coaches"):
        for row in session_worker.get("linked_coaches") or []:
            if row.get("is_active") and row.get("coach"):
                coach_name = (
                    frappe.db.get_value("Coach", row.coach, "coach_name")
                    or row.coach
                )

                context.linked_coaches.append({
                    "coach": row.coach,
                    "coach_name": coach_name,
                })

    context.show_invoice_cycle_start_date = (
        (session_worker.get("invoice_frequency") or "").strip() != "Monthly"
    )
