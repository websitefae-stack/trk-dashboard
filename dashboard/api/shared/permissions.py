import frappe
from frappe import _

from dashboard.api.shared.notifications import create_trk_notification


SESSION_WORKER_DOCTYPE = "Session Worker"
COACH_DOCTYPE = "Coach"

FRANCHISOR_USERS = {
    "ashley@theresilientkid.co.uk",
    "office@theresilientpeople.uk",
    "hq@theresilientkid.co.uk",
}


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


def get_current_session_worker():
    ensure_logged_in()

    session_worker_name = frappe.db.get_value(
        SESSION_WORKER_DOCTYPE,
        {"user": frappe.session.user},
        "name",
    )

    if not session_worker_name:
        session_worker_name = frappe.db.get_value(
            SESSION_WORKER_DOCTYPE,
            {"sw_email": frappe.session.user},
            "name",
        )

    if not session_worker_name:
        frappe.throw(_("No Session Worker profile is linked to your user."), frappe.PermissionError)

    return frappe.get_doc(SESSION_WORKER_DOCTYPE, session_worker_name)


def is_office_user():
    return frappe.session.user in FRANCHISOR_USERS


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


def get_expired_legal_items(doc, dashboard_type):
    expired = []
    today = frappe.utils.getdate(frappe.utils.today())

    if dashboard_type == "coach":
        legal_tables = [
            ("DBS", "dbs", "dbs_number"),
            ("DBS Update Service", "dbs_update_services", "dbs_number"),
            ("Insurance", "insurance", "insurance_number"),
            ("Indemnity", "indemnity", "indemnity_number"),
        ]
    elif dashboard_type == "session_worker":
        legal_tables = [
            ("DBS", "dbs", "dbs_number"),
            ("DBS Update Service", "dbs_update_service", "dbs_number"),
            ("Insurance", "insurance", "insurance_number"),
            ("Indemnity", "indemnity", "indemnity_number"),
        ]
    else:
        return expired

    for label, table_field, number_field in legal_tables:
        for row in doc.get(table_field) or []:
            expiry_date = row.get("expiry_date")

            if not expiry_date:
                continue

            try:
                expiry = frappe.utils.getdate(expiry_date)
            except Exception:
                continue

            if expiry < today:
                expired.append({
                    "label": label,
                    "number": row.get(number_field) or "",
                    "expiry_date": expiry_date,
                })

    return expired


def notify_franchisors_of_expired_legal(doc, dashboard_type, expired_items):
    if not expired_items:
        return

    cache_key = "legal_expiry_notification:{0}:{1}:{2}".format(
        dashboard_type,
        doc.name,
        frappe.utils.today(),
    )

    if frappe.cache().get_value(cache_key):
        return

    person_name = (
        doc.get("coach_name")
        or doc.get("sw_name")
        or doc.get("name")
    )

    message = "{0} has expired legal document(s): {1}".format(
        person_name,
        ", ".join([
            "{0} expired on {1}".format(item["label"], item["expiry_date"])
            for item in expired_items
        ]),
    )

    for user in FRANCHISOR_USERS:
        create_trk_notification(
            recipient_user=user,
            notification_type="Expired Legal Documents",
            message=message,
            priority="High",
            reference_doctype=doc.doctype,
            reference_name=doc.name,
            coach=doc.name if dashboard_type == "coach" else None,
            session_worker=doc.name if dashboard_type == "session_worker" else None,
        )

    frappe.cache().set_value(cache_key, 1, expires_in_sec=86400)


def is_profile_page_for_dashboard(dashboard_type):
    path = frappe.local.request.path if getattr(frappe.local, "request", None) else ""

    if dashboard_type == "coach":
        return path.startswith("/coach_db/profile")

    if dashboard_type == "session_worker":
        return path.startswith("/session_worker_db/profile")

    if dashboard_type == "franchisor":
        return path.startswith("/franchisor_db/profile")

    return False


def enforce_legal_compliance(dashboard_type):
    if dashboard_type == "franchisor":
        return

    if dashboard_type == "coach":
        doc = get_current_coach()
    elif dashboard_type == "session_worker":
        doc = get_current_session_worker()
    else:
        return

    expired_items = get_expired_legal_items(doc, dashboard_type)

    if not expired_items:
        return

    notify_franchisors_of_expired_legal(doc, dashboard_type, expired_items)

    if is_profile_page_for_dashboard(dashboard_type):
        return

    expired_text = ", ".join([
        "{0} expired on {1}".format(item["label"], item["expiry_date"])
        for item in expired_items
    ])

    frappe.throw(
        _("Your dashboard access is blocked because legal document(s) have expired: {0}. Please update your profile.").format(expired_text),
        frappe.PermissionError,
    )


def redirect_if_wrong_dashboard(expected):
    current = get_current_user_dashboard_type()

    if current == expected:
        enforce_legal_compliance(current)
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
