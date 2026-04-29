import frappe
from frappe import _


DOCTYPE = "TRK Notification"
VALID_STATUSES = ["Unread", "Read", "Archived"]


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
