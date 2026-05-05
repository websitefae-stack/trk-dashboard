import frappe

from dashboard.api.shared.permissions import (
    COACH_DOCTYPE,
    SESSION_WORKER_DOCTYPE,
    ensure_logged_in,
    get_current_coach_name,
)


def get_user_display_name():
    ensure_logged_in()
    return frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user


def get_coach_display_name():
    ensure_logged_in()

    coach_name = get_current_coach_name(optional=True)

    if coach_name:
        coach_label = frappe.db.get_value(COACH_DOCTYPE, coach_name, "coach_name")
        return coach_label or coach_name

    return get_user_display_name()


def get_franchisor_display_name():
    return get_user_display_name()


def get_session_workers():
    if not frappe.db.exists("DocType", SESSION_WORKER_DOCTYPE):
        return []

    return frappe.get_all(
        SESSION_WORKER_DOCTYPE,
        fields=["name"],
        order_by="name asc",
        limit_page_length=500,
    )


def get_coaches():
    if not frappe.db.exists("DocType", COACH_DOCTYPE):
        return []

    return frappe.get_all(
        COACH_DOCTYPE,
        fields=["name", "coach_name"],
        order_by="coach_name asc",
        limit_page_length=500,
    )
