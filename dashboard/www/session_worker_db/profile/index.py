import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.session_worker.profile import (
    get_session_worker_doc,
    get_session_worker_display_name,
)


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("session_worker")

    context.no_cache = 1
    context.page_title = "My Profile"
    context.active_page = "profile"

    session_worker = get_session_worker_doc()

    context.session_worker = session_worker
    context.dashboard_user_name = get_session_worker_display_name()
    context.dashboard_notifications_url = "/session_worker_db/notifications"

    context.dbs_rows = session_worker.get("dbs") or []
    context.dbs_update_service_rows = session_worker.get("dbs_update_service") or []
    context.insurance_rows = session_worker.get("insurance") or []
    context.indemnity_rows = session_worker.get("indemnity") or []

    context.linked_coaches = []
    for row in session_worker.get("linked_coaches") or []:
        if row.get("is_active") and row.get("coach"):
            coach_name = frappe.db.get_value("Coach", row.coach, "coach_name") or row.coach
            context.linked_coaches.append({
                "coach": row.coach,
                "coach_name": coach_name,
            })

    context.show_invoice_cycle_start_date = (
        (session_worker.invoice_frequency or "").strip() != "Monthly"
    )
