import frappe
from frappe import _

from dashboard.api.shared.notifications import create_trk_notification


SESSION_WORKER_DOCTYPE = "Session Worker"
COACH_DOCTYPE = "Coach"
CLIENT_DOCTYPE = "Client"

FRANCHISOR_USERS = {
    "ashley@theresilientkid.co.uk",
    "office@theresilienthub.co.uk",
    "hq@theresilientkid.co.uk",
}


# -------------------------------------------------------------------
# Basic user helpers
# -------------------------------------------------------------------

def ensure_logged_in():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def is_office_user():
    return frappe.session.user in FRANCHISOR_USERS


def is_franchisor_user():
    return is_office_user()


def ensure_office_user():
    ensure_logged_in()

    if not is_office_user():
        frappe.throw(_("You are not allowed to access this page."), frappe.PermissionError)


# -------------------------------------------------------------------
# Current user profile helpers
# -------------------------------------------------------------------

def get_current_coach_name(optional=False):
    ensure_logged_in()

    coach_name = frappe.db.get_value(COACH_DOCTYPE, {"user": frappe.session.user}, "name")

    if not coach_name:
        coach_name = frappe.db.get_value(COACH_DOCTYPE, {"coach_email": frappe.session.user}, "name")

    if not coach_name and not optional:
        frappe.throw(_("No Coach profile is linked to your user."), frappe.PermissionError)

    return coach_name or ""


def get_current_coach():
    coach_name = get_current_coach_name(optional=False)
    return frappe.get_doc(COACH_DOCTYPE, coach_name)


def get_current_session_worker_name(optional=False):
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

    if not session_worker_name and not optional:
        frappe.throw(_("No Session Worker profile is linked to your user."), frappe.PermissionError)

    return session_worker_name or ""


def get_current_session_worker():
    session_worker_name = get_current_session_worker_name(optional=False)
    return frappe.get_doc(SESSION_WORKER_DOCTYPE, session_worker_name)


def get_current_user_dashboard_type():
    ensure_logged_in()

    if is_office_user():
        return "franchisor"

    if frappe.db.exists(SESSION_WORKER_DOCTYPE, {"user": frappe.session.user}):
        return "session_worker"

    if frappe.db.exists(SESSION_WORKER_DOCTYPE, {"sw_email": frappe.session.user}):
        return "session_worker"

    if frappe.db.exists(COACH_DOCTYPE, {"user": frappe.session.user}):
        return "coach"

    if frappe.db.exists(COACH_DOCTYPE, {"coach_email": frappe.session.user}):
        return "coach"

    return "unknown"


# -------------------------------------------------------------------
# Client access helpers
# -------------------------------------------------------------------

def get_allowed_client_or_filters():
    """
    Returns:
    - None for franchisor/admin users because they can see all clients.
    - OR filters for coach/session worker access.
    - Safe empty filter for unknown users.
    """

    ensure_logged_in()

    if is_franchisor_user():
        return None

    dashboard_type = get_current_user_dashboard_type()

    if dashboard_type == "coach":
        coach_name = get_current_coach_name(optional=True)

        if not coach_name:
            return [[CLIENT_DOCTYPE, "name", "=", "__no_client__"]]

        return [
            [CLIENT_DOCTYPE, "primary_coach", "=", coach_name],
            [CLIENT_DOCTYPE, "attending_coach", "=", coach_name],
        ]

    if dashboard_type == "session_worker":
        session_worker_name = get_current_session_worker_name(optional=True)

        if not session_worker_name:
            return [[CLIENT_DOCTYPE, "name", "=", "__no_client__"]]

        return [
            [CLIENT_DOCTYPE, "session_worker", "=", session_worker_name],
        ]

    return [[CLIENT_DOCTYPE, "name", "=", "__no_client__"]]


def get_allowed_client_names():
    ensure_logged_in()

    or_filters = get_allowed_client_or_filters()

    if or_filters is None:
        return frappe.get_all(
            CLIENT_DOCTYPE,
            pluck="name",
            limit_page_length=5000,
        )

    return frappe.get_all(
        CLIENT_DOCTYPE,
        or_filters=or_filters,
        pluck="name",
        limit_page_length=5000,
    )


def user_can_access_client(client_name):
    ensure_logged_in()

    if not client_name:
        return False

    if is_franchisor_user():
        return True

    if not frappe.db.exists(CLIENT_DOCTYPE, client_name):
        return False

    client = frappe.db.get_value(
        CLIENT_DOCTYPE,
        client_name,
        [
            "name",
            "primary_coach",
            "attending_coach",
            "session_worker",
        ],
        as_dict=True,
    )

    if not client:
        return False

    dashboard_type = get_current_user_dashboard_type()

    if dashboard_type == "coach":
        coach_name = get_current_coach_name(optional=True)

        return coach_name in {
            client.get("primary_coach"),
            client.get("attending_coach"),
        }

    if dashboard_type == "session_worker":
        session_worker_name = get_current_session_worker_name(optional=True)

        return session_worker_name == client.get("session_worker")

    return False


def ensure_client_access(client_name):
    if not user_can_access_client(client_name):
        frappe.throw(_("You do not have permission to access this client."), frappe.PermissionError)

    return frappe.get_doc(CLIENT_DOCTYPE, client_name)


def get_client_role(client_name):
    """
    Returns the current user's relationship to a client.
    Possible values:
    - franchisor
    - primary_coach
    - attending_coach
    - session_worker
    - none
    """

    ensure_logged_in()

    if is_franchisor_user():
        return "franchisor"

    if not client_name or not frappe.db.exists(CLIENT_DOCTYPE, client_name):
        return "none"

    client = frappe.db.get_value(
        CLIENT_DOCTYPE,
        client_name,
        [
            "primary_coach",
            "attending_coach",
            "session_worker",
        ],
        as_dict=True,
    )

    dashboard_type = get_current_user_dashboard_type()

    if dashboard_type == "coach":
        coach_name = get_current_coach_name(optional=True)

        if coach_name and coach_name == client.get("primary_coach"):
            return "primary_coach"

        if coach_name and coach_name == client.get("attending_coach"):
            return "attending_coach"

    if dashboard_type == "session_worker":
        session_worker_name = get_current_session_worker_name(optional=True)

        if session_worker_name and session_worker_name == client.get("session_worker"):
            return "session_worker"

    return "none"


def get_client_permissions(client_name):
    """
    Central source of truth for what the current user can do with a client.
    """

    role = get_client_role(client_name)

    permissions = {
        "role": role,
        "can_view": False,
        "can_edit": False,
        "can_book": False,
        "can_invoice": False,
        "can_allocate": False,
        "can_view_contacts": False,
        "can_send_notifications": False,
        "invoice_company": "",
    }

    if role == "franchisor":
        permissions.update({
            "can_view": True,
            "can_edit": True,
            "can_book": True,
            "can_invoice": True,
            "can_allocate": True,
            "can_view_contacts": True,
            "can_send_notifications": True,
        })

    elif role == "primary_coach":
        permissions.update({
            "can_view": True,
            "can_edit": True,
            "can_book": True,
            "can_invoice": True,
            "can_allocate": True,
            "can_view_contacts": True,
            "can_send_notifications": True,
        })

    elif role == "attending_coach":
        permissions.update({
            "can_view": True,
            "can_edit": False,
            "can_book": True,
            "can_invoice": True,
            "can_allocate": False,
            "can_view_contacts": True,
            "can_send_notifications": True,
        })

    elif role == "session_worker":
        permissions.update({
            "can_view": True,
            "can_edit": False,
            "can_book": True,
            "can_invoice": False,
            "can_allocate": False,
            "can_view_contacts": True,
            "can_send_notifications": True,
        })

    if permissions["can_invoice"] and client_name and frappe.db.exists(CLIENT_DOCTYPE, client_name):
        primary_coach = frappe.db.get_value(CLIENT_DOCTYPE, client_name, "primary_coach")

        if primary_coach and frappe.db.exists(COACH_DOCTYPE, primary_coach):
            coach_meta = frappe.get_meta(COACH_DOCTYPE)

            if coach_meta.has_field("company"):
                permissions["invoice_company"] = frappe.db.get_value(COACH_DOCTYPE, primary_coach, "company") or ""

            elif coach_meta.has_field("coach_company"):
                permissions["invoice_company"] = frappe.db.get_value(COACH_DOCTYPE, primary_coach, "coach_company") or ""

    return permissions


# -------------------------------------------------------------------
# Session worker access helpers
# -------------------------------------------------------------------

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


# -------------------------------------------------------------------
# Legal compliance helpers
# -------------------------------------------------------------------

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


# -------------------------------------------------------------------
# Dashboard routing
# -------------------------------------------------------------------

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
