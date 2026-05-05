import frappe
from frappe import _
from frappe.utils import now_datetime


NOTIFICATION_DOCTYPE = "Notification Log"


def ensure_notification_access(notification_name):
    if not notification_name:
        frappe.throw(_("Notification not found"))

    if not frappe.db.exists(NOTIFICATION_DOCTYPE, notification_name):
        frappe.throw(_("Notification not found"))

    return True


def _format_notification(row):
    return {
        "name": row.get("name"),
        "notification_type": row.get("subject") or "Notification",
        "message": row.get("email_content") or row.get("subject") or "",
        "status": "Unread" if not row.get("read") else "Read",
        "priority": row.get("priority") or "Normal",
        "notification_date": row.get("creation"),
    }


def _get_filters():
    return {}


@frappe.whitelist()
def get_notifications(limit=20):
    rows = frappe.get_all(
        NOTIFICATION_DOCTYPE,
        filters=_get_filters(),
        fields=[
            "name",
            "subject",
            "email_content",
            "read",
            "priority",
            "creation",
        ],
        order_by="creation desc",
        limit_page_length=limit,
    )

    return [_format_notification(row) for row in rows]


@frappe.whitelist()
def get_notification_detail(name):
    ensure_notification_access(name)

    doc = frappe.get_doc(NOTIFICATION_DOCTYPE, name)

    return {
        "name": doc.name,
        "notification_type": doc.subject or "Notification",
        "message": doc.email_content or doc.subject or "",
        "status": "Unread" if not doc.read else "Read",
        "priority": doc.priority or "Normal",
        "notification_date": doc.creation,
    }


@frappe.whitelist()
def update_notification_status(name, read=1):
    ensure_notification_access(name)

    frappe.db.set_value(NOTIFICATION_DOCTYPE, name, "read", int(read))
    frappe.db.commit()

    return {"ok": True}


@frappe.whitelist()
def get_dashboard_notification_summary():
    rows = frappe.get_all(
        NOTIFICATION_DOCTYPE,
        filters=_get_filters(),
        fields=[
            "name",
            "subject",
            "email_content",
            "read",
            "priority",
            "creation",
        ],
        order_by="creation desc",
        limit_page_length=20,
    )

    latest = [_format_notification(row) for row in rows[:5]]
    unread_count = sum(1 for row in rows if not row.get("read"))

    return {
        "unread_count": unread_count,
        "latest": latest,
    }


def get_notification_summary_for_page(limit=5):
    rows = frappe.get_all(
        NOTIFICATION_DOCTYPE,
        filters=_get_filters(),
        fields=[
            "name",
            "subject",
            "email_content",
            "read",
            "priority",
            "creation",
        ],
        order_by="creation desc",
        limit_page_length=limit,
    )

    latest = [_format_notification(row) for row in rows]
    unread_count = sum(1 for row in rows if not row.get("read"))

    return {
        "unread_count": unread_count,
        "latest": latest,
    }


@frappe.whitelist()
def get_notification_list_for_page(limit=20):
    return get_notifications(limit=limit)


def get_notification_recipients():
    return []


@frappe.whitelist()
def send_dashboard_notification(subject, message, priority="Normal"):
    doc = frappe.get_doc({
        "doctype": NOTIFICATION_DOCTYPE,
        "subject": subject,
        "email_content": message,
        "priority": priority,
        "read": 0,
    })

    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "ok": True,
        "name": doc.name,
    }
