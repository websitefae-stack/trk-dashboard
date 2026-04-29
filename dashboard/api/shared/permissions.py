import frappe
from frappe import _


SESSION_WORKER_DOCTYPE = "Session Worker"
COACH_DOCTYPE = "Coach"


def ensure_logged_in():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def get_current_coach():
    ensure_logged_in()

    coach_name = frappe.db.get_value(COACH_DOCTYPE, {"user": frappe.session.user}, "name")

    if not coach_name:
        coach_name = frappe.db.get_value(COACH_DOCTYPE, {"coach_email": frappe.session.user}, "name")

    if not coach_name:
        frappe.throw(_("No Coach profile is linked to your user."), frappe.PermissionError)

    return frappe.get_doc(COACH_DOCTYPE, coach_name)


def is_office_user():
    return frappe.session.user in {
        "ashley@theresilientkid.co.uk",
        "office@theresilientpeople.uk",
        "hq@theresilientkid.co.uk",
    }


def ensure_office_user():
    ensure_logged_in()

    if not is_office_user():
        frappe.throw(_("You are not allowed to access this page."), frappe.PermissionError)


def get_active_session_worker_coaches(session_worker):
    coaches = []

    for row in session_worker.get("linked_coaches") or []:
        if row.get("is_active") and row.get("coach"):
            coaches.append(row.coach)

    return coaches


def coach_can_access_session_worker(session_worker_name):
    ensure_logged_in()

    coach = get_current_coach()
    session_worker = frappe.get_doc(SESSION_WORKER_DOCTYPE, session_worker_name)

    linked_coaches = get_active_session_worker_coaches(session_worker)

    return coach.name in linked_coaches


def ensure_coach_can_access_session_worker(session_worker_name):
    if not coach_can_access_session_worker(session_worker_name):
        frappe.throw(_("You are not allowed to access this Session Worker."), frappe.PermissionError)

    return frappe.get_doc(SESSION_WORKER_DOCTYPE, session_worker_name)


def ensure_franchisor_can_access_session_worker(session_worker_name):
    ensure_office_user()
    return frappe.get_doc(SESSION_WORKER_DOCTYPE, session_worker_name)


def ensure_franchisor_can_access_coach(coach_name):
    ensure_office_user()
    return frappe.get_doc(COACH_DOCTYPE, coach_name)

def get_current_user_dashboard_type():
    ensure_logged_in()

    if is_office_user():
        return "franchisor"

    if frappe.db.exists("Session Worker", {"user": frappe.session.user}):
        return "session_worker"

    if frappe.db.exists("Session Worker", {"sw_email": frappe.session.user}):
        return "session_worker"

    if frappe.db.exists("Coach", {"user": frappe.session.user}):
        return "coach"

    if frappe.db.exists("Coach", {"coach_email": frappe.session.user}):
        return "coach"

    return "unknown"


def redirect_if_wrong_dashboard(expected):
    current = get_current_user_dashboard_type()

    if current == expected:
        return

    if current == "session_worker":
        frappe.local.flags.redirect_location = "/session_worker_db"
        raise frappe.Redirect

    if current == "coach":
        frappe.local.flags.redirect_location = "/coach_db"
        raise frappe.Redirect

    if current == "franchisor":
        frappe.local.flags.redirect_location = "/franchisor_db"
        raise frappe.Redirect

    frappe.throw(_("You are not allowed to access this dashboard."), frappe.PermissionError)
