import frappe
from frappe import _
from trk_session_worker_dashboard.api.clients import _find_session_worker_for_user
from dashboard.api.coach.clients import get_coach_record


def get_current_user_dashboard_type():
    if frappe.session.user == "Guest":
        return "guest"

    if _find_session_worker_for_user(frappe.session.user):
        return "session_worker"

    if get_coach_record(frappe.session.user):
        return "coach"

    return "franchisor"


def redirect_if_wrong_dashboard(expected):
    current = get_current_user_dashboard_type()

    if current == "guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    if current == expected:
        return

    if current == "coach":
        frappe.local.flags.redirect_location = "/coach_db"
        raise frappe.Redirect

    if current == "franchisor":
        frappe.local.flags.redirect_location = "/franchisor_db"
        raise frappe.Redirect

    if current == "session_worker":
        frappe.local.flags.redirect_location = "/session_worker_db"
        raise frappe.Redirect
