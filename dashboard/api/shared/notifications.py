import frappe
from frappe import _


DOCTYPE = "TRK Notification"
VALID_STATUSES = ["Unread", "Read", "Archived"]


def ensure_logged_in():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def create_trk_notification(
    recipient_user,
    notification_type,
    message,
    priority="Normal",
    reference_doctype=None,
    reference_name=None,
    coach=None,
    session_worker=None,
    client=None,
    sent_from=None,
):
    if not recipient_user:
        return None

    if not frappe.db.exists("User", recipient_user):
        frappe.log_error(
            f"Notification recipient does not exist: {recipient_user}",
            "Dashboard Notification Error",
        )
        return None

    doc = frappe.get_doc({
        "doctype": DOCTYPE,
        "recipient_user": recipient_user,
        "notification_type": notification_type,
        "message": message,
        "status": "Unread",
        "priority": priority,
        "notification_date": frappe.utils.now_datetime(),
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "coach": coach,
        "session_worker": session_worker,
        "client": client,
        "sent_from": sent_from or frappe.session.user,
    })

    doc.insert(ignore_permissions=True)
    return doc.name


def get_current_user():
    return frappe.session.user


def ensure_notification_access(notification_name):
    ensure_logged_in()

    doc = frappe.get_doc(DOCTYPE, notification_name)

    if doc.recipient_user != get_current_user():
        frappe.throw(_("You are not allowed to access this notification."), frappe.PermissionError)

    return doc


def get_notification_list_for_page(status=None, limit=100):
    ensure_logged_in()

    filters = {
        "recipient_user": get_current_user()
    }

    if status == "Active":
        filters["status"] = ["!=", "Archived"]
    elif status and status != "All":
        filters["status"] = status

    return frappe.get_all(
        DOCTYPE,
        filters=filters,
        fields=[
            "name",
            "recipient_user",
            "notification_type",
            "message",
            "client",
            "coach",
            "session_worker",
            "event",
            "client_package",
            "client_package_balance",
            "status",
            "notification_date",
            "priority",
            "reference_name",
            "sent_from",
            "creation",
            "reference_doctype",
        ],
        order_by="notification_date desc, creation desc",
        limit_page_length=int(limit or 100),
    )


def get_notification_summary_for_page(limit=5):
    ensure_logged_in()

    unread_count = frappe.db.count(DOCTYPE, {
        "recipient_user": get_current_user(),
        "status": ["!=", "Archived"],
    })

    latest = get_notification_list_for_page(status="Active", limit=limit)

    return {
        "unread_count": unread_count,
        "latest": latest,
    }


@frappe.whitelist()
def get_notifications(status="All"):
    return get_notification_list_for_page(status=status, limit=100)


@frappe.whitelist()
def get_notification_detail(name):
    doc = ensure_notification_access(name)
    return doc.as_dict()


@frappe.whitelist()
def update_notification_status(name, status):
    if status not in VALID_STATUSES:
        frappe.throw(_("Invalid notification status."))

    doc = ensure_notification_access(name)
    doc.status = status
    doc.save(ignore_permissions=True)

    return {
        "name": doc.name,
        "status": doc.status,
    }


@frappe.whitelist()
def get_dashboard_notification_summary():
    return get_notification_summary_for_page(limit=5)
