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

    redirect_if_wrong_dashboard("session_worker")

    profile_context = get_profile_context("session_worker")

    session_worker = profile_context["profile_doc"]

    context.no_cache = 1
    context.page_title = "My Profile"
    context.active_page = "profile"

    context.profile_role = "session_worker"

    context.session_worker = session_worker
    context.profile_doc = session_worker
    context.user_doc = profile_context["user_doc"]

    context.dashboard_user_name = get_profile_display_name("session_worker")
    context.dashboard_notifications_url = "/session_worker_db/notifications"

    context.bank_account = profile_context["bank_account"]

    context.dbs_rows = profile_context["dbs_rows"]
    context.dbs_update_service_rows = profile_context["dbs_update_service_rows"]
    context.insurance_rows = profile_context["insurance_rows"]
    context.indemnity_rows = profile_context["indemnity_rows"]

    context.linked_coaches = []

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
        (session_worker.invoice_frequency or "").strip() != "Monthly"
    )
