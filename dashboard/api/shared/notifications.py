import frappe
from frappe import _
from frappe.utils import now_datetime


NOTIFICATION_DOCTYPE = "Notification Log"


def ensure_logged_in():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def _field_exists(fieldname):
    return frappe.get_meta(NOTIFICATION_DOCTYPE).has_field(fieldname)


def _get_current_user_filter():
    """
    Notification Log usually has a 'for_user' field.
    If it exists, users should only see their own notifications.
    Office/franchisor visibility can be widened later if needed.
    """
    if _field_exists("for_user"):
        return {"for_user": frappe.session.user}

    return {}


def _get_filters(status=None):
    filters = _get_current_user_filter()

    if status and status != "All":
        if status == "Unread" and _field_exists("read"):
            filters["read"] = 0

        elif status == "Read" and _field_exists("read"):
            filters["read"] = 1

    return filters


def _format_notification(row):
    read_value = row.get("read")

    return {
        "name": row.get("name"),
        "notification_type": row.get("subject") or row.get("type") or "Notification",
        "message": row.get("email_content") or row.get("subject") or "",
        "status": "Unread" if not read_value else "Read",
        "priority": row.get("priority") or "Normal",
        "notification_date": row.get("creation"),
        "client": row.get("document_name") if row.get("document_type") == "Client" else "",
        "coach": "",
        "session_worker": "",
        "event": "",
        "client_package": "",
        "client_package_balance": "",
        "reference_doctype": row.get("document_type") or "",
        "reference_name": row.get("document_name") or "",
        "sent_from": row.get("from_user") or "",
    }


def _notification_fields():
    fields = [
        "name",
        "subject",
        "email_content",
        "read",
        "creation",
    ]

    optional_fields = [
        "priority",
        "type",
        "document_type",
        "document_name",
        "from_user",
        "for_user",
    ]

    for fieldname in optional_fields:
        if _field_exists(fieldname):
            fields.append(fieldname)

    return fields


def ensure_notification_access(notification_name):
    ensure_logged_in()

    if not notification_name:
        frappe.throw(_("Notification not found."))

    if not frappe.db.exists(NOTIFICATION_DOCTYPE, notification_name):
        frappe.throw(_("Notification not found."))

    doc = frappe.get_doc(NOTIFICATION_DOCTYPE, notification_name)

    if _field_exists("for_user") and doc.get("for_user") and doc.get("for_user") != frappe.session.user:
        frappe.throw(_("You do not have permission to access this notification."), frappe.PermissionError)

    return doc


@frappe.whitelist()
def get_notifications(status="All", limit=20):
    ensure_logged_in()

    rows = frappe.get_all(
        NOTIFICATION_DOCTYPE,
        filters=_get_filters(status),
        fields=_notification_fields(),
        order_by="creation desc",
        limit_page_length=int(limit or 20),
    )

    return [_format_notification(row) for row in rows]


@frappe.whitelist()
def get_notification_detail(name):
    doc = ensure_notification_access(name)
    return _format_notification(doc.as_dict())


@frappe.whitelist()
def update_notification_status(name, status=None, read=None):
    doc = ensure_notification_access(name)

    if read is None:
        read = 1 if status == "Read" else 0

    frappe.db.set_value(NOTIFICATION_DOCTYPE, doc.name, "read", int(read))
    frappe.db.commit()

    return {"ok": True}


@frappe.whitelist()
def get_dashboard_notification_summary():
    return get_notification_summary_for_page(limit=5)


def get_notification_summary_for_page(limit=5):
    ensure_logged_in()

    rows = frappe.get_all(
        NOTIFICATION_DOCTYPE,
        filters=_get_filters(),
        fields=_notification_fields(),
        order_by="creation desc",
        limit_page_length=int(limit or 5),
    )

    latest = [_format_notification(row) for row in rows]
    unread_count = sum(1 for row in rows if not row.get("read"))

    return {
        "unread_count": unread_count,
        "latest": latest,
    }


@frappe.whitelist()
def get_notification_list_for_page(status="All", limit=20):
    return get_notifications(status=status, limit=limit)


def get_notification_recipients():
    """
    Keep this simple for now.
    We can make it permission-aware later.
    """
    admins = []
    coaches = []
    session_workers = []

    for email in [
        "ashley@theresilientkid.co.uk",
        "office@theresilientpeople.uk",
        "hq@theresilientkid.co.uk",
    ]:
        if frappe.db.exists("User", email):
            admins.append({
                "recipient_user": email,
                "label": frappe.get_cached_value("User", email, "full_name") or email,
            })

    if frappe.db.exists("DocType", "Coach"):
        coach_fields = ["name"]
        if frappe.get_meta("Coach").has_field("coach_name"):
            coach_fields.append("coach_name")
        if frappe.get_meta("Coach").has_field("user"):
            coach_fields.append("user")
        if frappe.get_meta("Coach").has_field("coach_email"):
            coach_fields.append("coach_email")

        for coach in frappe.get_all("Coach", fields=coach_fields, limit_page_length=500):
            recipient = coach.get("user") or coach.get("coach_email")
            if recipient:
                coaches.append({
                    "recipient_user": recipient,
                    "label": coach.get("coach_name") or coach.get("name"),
                })

    if frappe.db.exists("DocType", "Session Worker"):
        sw_fields = ["name"]
        if frappe.get_meta("Session Worker").has_field("sw_name"):
            sw_fields.append("sw_name")
        if frappe.get_meta("Session Worker").has_field("user"):
            sw_fields.append("user")
        if frappe.get_meta("Session Worker").has_field("sw_email"):
            sw_fields.append("sw_email")

        for sw in frappe.get_all("Session Worker", fields=sw_fields, limit_page_length=500):
            recipient = sw.get("user") or sw.get("sw_email")
            if recipient:
                session_workers.append({
                    "recipient_user": recipient,
                    "label": sw.get("sw_name") or sw.get("name"),
                })

    return {
        "admins": admins,
        "coaches": coaches,
        "session_workers": session_workers,
    }


@frappe.whitelist()
def send_dashboard_notification(
    recipient_users=None,
    notification_type="Dashboard Message",
    message=None,
    priority="Normal",
    subject=None,
):
    ensure_logged_in()

    if isinstance(recipient_users, str):
        try:
            recipient_users = frappe.parse_json(recipient_users)
        except Exception:
            recipient_users = [recipient_users]

    recipient_users = recipient_users or []

    if not recipient_users:
        frappe.throw(_("Please select at least one recipient."))

    if not message:
        frappe.throw(_("Please enter a message."))

    created = []

    for recipient_user in recipient_users:
        doc_data = {
            "doctype": NOTIFICATION_DOCTYPE,
            "subject": subject or notification_type,
            "email_content": message,
            "read": 0,
        }

        if _field_exists("for_user"):
            doc_data["for_user"] = recipient_user

        if _field_exists("from_user"):
            doc_data["from_user"] = frappe.session.user

        if _field_exists("type"):
            doc_data["type"] = notification_type

        if _field_exists("priority"):
            doc_data["priority"] = priority

        doc = frappe.get_doc(doc_data)
        doc.insert(ignore_permissions=True)
        created.append(doc.name)

    frappe.db.commit()

    return {
        "ok": True,
        "message": "Notification sent.",
        "created": created,
    }


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
    event=None,
):
    """
    Used by permissions.py for legal expiry notifications.
    """
    if not recipient_user:
        return None

    doc_data = {
        "doctype": NOTIFICATION_DOCTYPE,
        "subject": notification_type or "Dashboard Notification",
        "email_content": message or "",
        "read": 0,
    }

    if _field_exists("for_user"):
        doc_data["for_user"] = recipient_user

    if _field_exists("from_user"):
        doc_data["from_user"] = frappe.session.user

    if _field_exists("type"):
        doc_data["type"] = notification_type

    if _field_exists("priority"):
        doc_data["priority"] = priority

    if _field_exists("document_type") and reference_doctype:
        doc_data["document_type"] = reference_doctype

    if _field_exists("document_name") and reference_name:
        doc_data["document_name"] = reference_name

    doc = frappe.get_doc(doc_data)
    doc.insert(ignore_permissions=True)

    return doc.name
