import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.directory import get_franchisor_display_name

# Diagnostic/repair tools (Appointment Integrity Report and the duplicate
# Event repair action) stay restricted to this single office user, per the
# original design - they can permanently delete Events. The Forms report
# below is read-only and open to every franchisor user; the API layer
# (packages.py's _ensure_reports_access) independently enforces the same
# office@-only restriction for the diagnostic endpoints regardless of what
# this page renders, so this is UI-level tidiness, not the security
# boundary itself.
OFFICE_USER = "office@theresilienthub.co.uk"


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    context.no_cache = 1
    context.page_title = "Reports"
    context.active_page = "reports"
    context.dashboard_base_url = "/franchisor_db"
    context.dashboard_type = "franchisor"
    context.can_view_diagnostics = 1 if frappe.session.user == OFFICE_USER else 0

    try:
        context.dashboard_user_name = get_franchisor_display_name()
    except Exception:
        context.dashboard_user_name = frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user
