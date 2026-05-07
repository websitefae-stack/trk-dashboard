import frappe
from frappe import _
from frappe.utils import now_datetime


CONVERSATION_DOCTYPE = "Dashboard Conversation"
RECIPIENT_CHILD_DOCTYPE = "Dashboard Conversation Recipient"
REPLY_CHILD_DOCTYPE = "Dashboard Conversation Reply"

NOTIFICATION_DOCTYPE = "Notification Log"

FRANCHISOR_USERS = [
    "ashley@theresilientkid.co.uk",
    "hq@theresilientkid.co.uk",
    "office@theresilientpeople.uk",
]


def ensure_logged_in():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def _conversation_enabled():
    return frappe.db.exists("DocType", CONVERSATION_DOCTYPE)


def _field_exists(doctype, fieldname):
    if not frappe.db.exists("DocType", doctype):
        return False

    return frappe.get_meta(doctype).has_field(fieldname)


def _is_franchisor_user(user=None):
    user = (user or frappe.session.user or "").strip().lower()
    return user in {email.lower() for email in FRANCHISOR_USERS}


def _get_user_full_name(user):
    if not user:
        return ""

    return frappe.get_cached_value("User", user, "full_name") or user


def _get_current_role():
    user = frappe.session.user

    if _is_franchisor_user(user):
        return "Franchisor"

    if _get_current_coach_name(user):
        return "Coach"

    if _get_current_session_worker_name(user):
        return "Session Worker"

    return "Admin"


def _get_current_coach_name(user=None):
    user = user or frappe.session.user

    if not frappe.db.exists("DocType", "Coach"):
        return ""

    meta = frappe.get_meta("Coach")

    for fieldname in ["user", "user_id", "email", "coach_email"]:
        if meta.has_field(fieldname):
            coach = frappe.db.get_value("Coach", {fieldname: user}, "name")
            if coach:
                return coach

    return ""


def _get_current_session_worker_name(user=None):
    user = user or frappe.session.user

    if not frappe.db.exists("DocType", "Session Worker"):
        return ""

    meta = frappe.get_meta("Session Worker")

    for fieldname in ["user", "user_id", "email", "session_worker_email", "sw_email"]:
        if meta.has_field(fieldname):
            worker = frappe.db.get_value("Session Worker", {fieldname: user}, "name")
            if worker:
                return worker

    return ""


def _get_label(row, fields):
    for fieldname in fields:
        value = (row.get(fieldname) or "").strip()
        if value:
            return value

    return row.get("name") or ""


def _get_coach_user_and_label(row):
    user = ""

    for fieldname in ["user", "user_id", "email", "coach_email"]:
        if row.get(fieldname):
            user = row.get(fieldname)
            break

    label = _get_label(
        row,
        ["coach_name", "full_name", "employee_name", "user_full_name", "title", "name"],
    )

    return user, label


def _get_session_worker_user_and_label(row):
    user = ""

    for fieldname in ["user", "user_id", "email", "session_worker_email", "sw_email"]:
        if row.get(fieldname):
            user = row.get(fieldname)
            break

    label = _get_label(
        row,
        ["sw_name", "session_worker_name", "full_name", "employee_name", "user_full_name", "title", "name"],
    )

    return user, label


def _get_all_coaches():
    if not frappe.db.exists("DocType", "Coach"):
        return []

    meta = frappe.get_meta("Coach")
    fields = ["name"]

    for fieldname in [
        "coach_name",
        "full_name",
        "employee_name",
        "user_full_name",
        "title",
        "user",
        "user_id",
        "email",
        "coach_email",
    ]:
        if meta.has_field(fieldname) and fieldname not in fields:
            fields.append(fieldname)

    rows = frappe.get_all(
        "Coach",
        fields=fields,
        order_by="name asc",
        limit_page_length=1000,
        ignore_permissions=True,
    )

    result = []

    for row in rows:
        user, label = _get_coach_user_and_label(row)

        if not user:
            continue

        result.append({
            "recipient_user": user,
            "label": label,
            "role": "Coach",
            "source_doctype": "Coach",
            "source_name": row.get("name"),
        })

    return result


def _get_all_session_workers():
    if not frappe.db.exists("DocType", "Session Worker"):
        return []

    meta = frappe.get_meta("Session Worker")
    fields = ["name"]

    for fieldname in [
        "sw_name",
        "session_worker_name",
        "full_name",
        "employee_name",
        "user_full_name",
        "title",
        "user",
        "user_id",
        "email",
        "session_worker_email",
        "sw_email",
    ]:
        if meta.has_field(fieldname) and fieldname not in fields:
            fields.append(fieldname)

    rows = frappe.get_all(
        "Session Worker",
        fields=fields,
        order_by="name asc",
        limit_page_length=1000,
        ignore_permissions=True,
    )

    result = []

    for row in rows:
        user, label = _get_session_worker_user_and_label(row)

        if not user:
            continue

        result.append({
            "recipient_user": user,
            "label": label,
            "role": "Session Worker",
            "source_doctype": "Session Worker",
            "source_name": row.get("name"),
        })

    return result


def _get_admin_recipients():
    result = []

    for email in FRANCHISOR_USERS:
        if frappe.db.exists("User", email):
            result.append({
                "recipient_user": email,
                "label": _get_user_full_name(email),
                "role": "Franchisor",
                "source_doctype": "User",
                "source_name": email,
            })

    return result


def _get_client_meta():
    if not frappe.db.exists("DocType", "Client"):
        return None

    return frappe.get_meta("Client")


def _get_session_workers_linked_to_coach(coach_name):
    if not coach_name:
        return set()

    meta = _get_client_meta()
    if not meta:
        return set()

    if not meta.has_field("session_worker"):
        return set()

    worker_names = set()

    if meta.has_field("primary_coach"):
        rows = frappe.get_all(
            "Client",
            filters={"primary_coach": coach_name},
            pluck="session_worker",
            limit_page_length=5000,
            ignore_permissions=True,
        )
        worker_names.update([row for row in rows if row])

    if meta.has_field("attending_coach"):
        rows = frappe.get_all(
            "Client",
            filters={"attending_coach": coach_name},
            pluck="session_worker",
            limit_page_length=5000,
            ignore_permissions=True,
        )
        worker_names.update([row for row in rows if row])

    return worker_names


def _get_coaches_linked_to_session_worker(worker_name):
    if not worker_name:
        return set()

    meta = _get_client_meta()
    if not meta:
        return set()

    if not meta.has_field("session_worker"):
        return set()

    coach_names = set()
    fields = ["name"]

    if meta.has_field("primary_coach"):
        fields.append("primary_coach")

    if meta.has_field("attending_coach"):
        fields.append("attending_coach")

    rows = frappe.get_all(
        "Client",
        fields=fields,
        filters={"session_worker": worker_name},
        limit_page_length=5000,
        ignore_permissions=True,
    )

    for row in rows:
        if row.get("primary_coach"):
            coach_names.add(row.get("primary_coach"))

        if row.get("attending_coach"):
            coach_names.add(row.get("attending_coach"))

    return coach_names


def _filter_session_workers_by_names(worker_names):
    worker_names = set(worker_names or [])

    if not worker_names:
        return []

    return [
        row for row in _get_all_session_workers()
        if row.get("source_name") in worker_names
    ]


def _filter_coaches_by_names(coach_names):
    coach_names = set(coach_names or [])

    if not coach_names:
        return []

    return [
        row for row in _get_all_coaches()
        if row.get("source_name") in coach_names
    ]


def _dedupe_recipients(rows):
    seen = set()
    result = []

    for row in rows or []:
        user = row.get("recipient_user")
        if not user or user in seen:
            continue

        seen.add(user)
        result.append(row)

    return result


@frappe.whitelist()
def get_notification_recipients():
    """
    Recipient list is intentionally NOT all Users.

    Allowed recipient sources only:
    - approved franchisor/admin users
    - Coach DocType records with a linked user/email
    - Session Worker DocType records with a linked user/email
    """
    ensure_logged_in()

    current_user = frappe.session.user
    current_role = _get_current_role()

    admins = _get_admin_recipients()
    coaches = []
    session_workers = []

    if current_role in ["Franchisor", "Admin"]:
        coaches = _get_all_coaches()
        session_workers = _get_all_session_workers()

    elif current_role == "Coach":
        coach_name = _get_current_coach_name(current_user)

        coaches = [
            row for row in _get_all_coaches()
            if row.get("recipient_user") != current_user
        ]

        linked_workers = _get_session_workers_linked_to_coach(coach_name)
        session_workers = _filter_session_workers_by_names(linked_workers)

    elif current_role == "Session Worker":
        worker_name = _get_current_session_worker_name(current_user)
        linked_coaches = _get_coaches_linked_to_session_worker(worker_name)

        coaches = _filter_coaches_by_names(linked_coaches)
        session_workers = []

    return {
        "admins": _dedupe_recipients(admins),
        "coaches": _dedupe_recipients(coaches),
        "session_workers": _dedupe_recipients(session_workers),
        "current_role": current_role,
    }


def _get_request_payload():
    payload = {}

    try:
        if getattr(frappe, "request", None):
            payload = frappe.request.get_json(silent=True) or {}
    except Exception:
        payload = {}

    return payload if isinstance(payload, dict) else {}


def _coalesce_raw(fieldname, explicit_value=None):
    if explicit_value not in (None, ""):
        return explicit_value

    payload = _get_request_payload()

    if fieldname in payload and payload.get(fieldname) not in (None, ""):
        return payload.get(fieldname)

    form_value = frappe.form_dict.get(fieldname)

    if form_value not in (None, ""):
        return form_value

    return explicit_value


def _coalesce_str(fieldname, explicit_value=None):
    value = _coalesce_raw(fieldname, explicit_value)
    return (value or "").strip() if isinstance(value, str) else (str(value).strip() if value not in (None, "") else "")


def _normalise_recipient_users(recipient_users):
    if isinstance(recipient_users, str):
        try:
            recipient_users = frappe.parse_json(recipient_users)
        except Exception:
            recipient_users = [recipient_users]

    return [row for row in (recipient_users or []) if row]


def _allowed_recipient_user_set():
    recipients = get_notification_recipients()

    users = set()

    for group in ["admins", "coaches", "session_workers"]:
        for row in recipients.get(group) or []:
            if row.get("recipient_user"):
                users.add(row.get("recipient_user"))

    return users


def _get_recipient_role(recipient_user):
    for row in _get_admin_recipients():
        if row.get("recipient_user") == recipient_user:
            return row.get("role") or "Franchisor"

    for row in _get_all_coaches():
        if row.get("recipient_user") == recipient_user:
            return "Coach"

    for row in _get_all_session_workers():
        if row.get("recipient_user") == recipient_user:
            return "Session Worker"

    return ""


def _get_reference_link(reference_doctype, reference_name, dashboard_base_url=""):
    if not reference_doctype or not reference_name:
        return ""

    if reference_doctype == "Client":
        return f"{dashboard_base_url}/client_details?name={reference_name}" if dashboard_base_url else ""

    if reference_doctype == "Event":
        return f"{dashboard_base_url}/calendar_details?event={reference_name}" if dashboard_base_url else ""

    return ""


def _get_dashboard_base_url():
    role = _get_current_role()

    if role == "Coach":
        return "/coach_db"

    if role == "Session Worker":
        return "/session_worker_db"

    return "/franchisor_db"


def _user_is_recipient(doc, user):
    for row in doc.get("recipients") or []:
        if row.get("recipient_user") == user:
            return True

    return False


def _get_recipient_row(doc, user):
    for row in doc.get("recipients") or []:
        if row.get("recipient_user") == user:
            return row

    return None


def ensure_notification_access(notification_name):
    ensure_logged_in()

    if not notification_name:
        frappe.throw(_("Notification not found."))

    if _conversation_enabled() and frappe.db.exists(CONVERSATION_DOCTYPE, notification_name):
        doc = frappe.get_doc(CONVERSATION_DOCTYPE, notification_name)

        if doc.get("created_by_user") == frappe.session.user:
            return doc

        if _user_is_recipient(doc, frappe.session.user):
            return doc

        if _is_franchisor_user():
            return doc

        frappe.throw(_("You do not have permission to access this notification."), frappe.PermissionError)

    if frappe.db.exists(NOTIFICATION_DOCTYPE, notification_name):
        doc = frappe.get_doc(NOTIFICATION_DOCTYPE, notification_name)

        if _field_exists(NOTIFICATION_DOCTYPE, "for_user") and doc.get("for_user") and doc.get("for_user") != frappe.session.user:
            frappe.throw(_("You do not have permission to access this notification."), frappe.PermissionError)

        return doc

    frappe.throw(_("Notification not found."))


def _format_conversation(doc):
    current_user = frappe.session.user
    recipient_row = _get_recipient_row(doc, current_user)

    is_read = 1

    if doc.get("created_by_user") != current_user:
        is_read = int(recipient_row.get("read") or 0) if recipient_row else 0

    linked_client = doc.get("linked_client") or ""
    linked_event = doc.get("linked_event") or ""
    reference_doctype = doc.get("reference_doctype") or ""
    reference_name = doc.get("reference_name") or ""

    dashboard_base_url = _get_dashboard_base_url()

    client_link = f"{dashboard_base_url}/client_details?name={linked_client}" if linked_client else ""
    event_link = f"{dashboard_base_url}/calendar_details?event={linked_event}" if linked_event else ""

    return {
        "name": doc.get("name"),
        "notification_type": doc.get("conversation_type") or "Message",
        "conversation_type": doc.get("conversation_type") or "Message",
        "title": doc.get("title") or doc.get("conversation_type") or "Notification",
        "message": doc.get("message") or "",
        "status": doc.get("status") or "Open",
        "read_status": "Read" if is_read else "Unread",
        "priority": doc.get("priority") or "Normal",
        "notification_date": doc.get("creation"),
        "created_by_user": doc.get("created_by_user") or "",
        "created_by_label": _get_user_full_name(doc.get("created_by_user") or ""),
        "created_by_role": doc.get("created_by_role") or "",
        "client": linked_client,
        "event": linked_event,
        "coach": "",
        "session_worker": "",
        "client_package": "",
        "client_package_balance": "",
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "requires_response": int(doc.get("requires_response") or 0),
        "due_date": doc.get("due_date"),
        "sent_from": doc.get("created_by_user") or "",
        "client_link": client_link,
        "event_link": event_link,
        "reference_link": _get_reference_link(reference_doctype, reference_name, dashboard_base_url),
        "reply_count": len(doc.get("replies") or []),
        "recipients": [
            {
                "recipient_user": row.get("recipient_user"),
                "recipient_label": _get_user_full_name(row.get("recipient_user")),
                "recipient_role": row.get("recipient_role") or "",
                "read": int(row.get("read") or 0),
                "read_on": row.get("read_on"),
                "archived": int(row.get("archived") or 0),
            }
            for row in doc.get("recipients") or []
        ],
        "replies": [
            {
                "reply_user": row.get("reply_user"),
                "reply_user_label": _get_user_full_name(row.get("reply_user")),
                "reply_user_role": row.get("reply_user_role") or "",
                "message": row.get("message") or "",
                "creation": row.get("creation"),
                "idx": row.get("idx") or 0,
            }
            for row in doc.get("replies") or []
        ],
    }


def _format_notification_log(row):
    read_value = row.get("read")

    return {
        "name": row.get("name"),
        "notification_type": row.get("subject") or row.get("type") or "Notification",
        "conversation_type": row.get("type") or "Notification",
        "title": row.get("subject") or row.get("type") or "Notification",
        "message": row.get("email_content") or row.get("subject") or "",
        "status": "Unread" if not read_value else "Read",
        "read_status": "Unread" if not read_value else "Read",
        "priority": row.get("priority") or "Normal",
        "notification_date": row.get("creation"),
        "client": row.get("document_name") if row.get("document_type") == "Client" else "",
        "coach": "",
        "session_worker": "",
        "event": row.get("document_name") if row.get("document_type") == "Event" else "",
        "client_package": "",
        "client_package_balance": "",
        "reference_doctype": row.get("document_type") or "",
        "reference_name": row.get("document_name") or "",
        "sent_from": row.get("from_user") or "",
        "reply_count": 0,
        "recipients": [],
        "replies": [],
    }


def _notification_log_fields():
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
        if _field_exists(NOTIFICATION_DOCTYPE, fieldname):
            fields.append(fieldname)

    return fields


def _get_notification_log_filters(status=None):
    filters = {}

    if _field_exists(NOTIFICATION_DOCTYPE, "for_user"):
        filters["for_user"] = frappe.session.user

    if status and status != "All":
        if status == "Unread" and _field_exists(NOTIFICATION_DOCTYPE, "read"):
            filters["read"] = 0
        elif status == "Read" and _field_exists(NOTIFICATION_DOCTYPE, "read"):
            filters["read"] = 1

    return filters


def _current_user_can_see_conversation(doc):
    if doc.get("created_by_user") == frappe.session.user:
        return True

    if _user_is_recipient(doc, frappe.session.user):
        return True

    if _is_franchisor_user():
        return True

    return False


def _conversation_matches_status(doc, status):
    if not status or status == "All":
        return True

    if status in ["Open", "Waiting", "In Progress", "Done", "Archived"]:
        return (doc.get("status") or "Open") == status

    if status in ["Read", "Unread"]:
        formatted = _format_conversation(doc)
        return formatted.get("read_status") == status

    return True


@frappe.whitelist()
def get_notifications(status="All", limit=20):
    ensure_logged_in()

    if not _conversation_enabled():
        rows = frappe.get_all(
            NOTIFICATION_DOCTYPE,
            filters=_get_notification_log_filters(status),
            fields=_notification_log_fields(),
            order_by="creation desc",
            limit_page_length=int(limit or 20),
        )
        return [_format_notification_log(row) for row in rows]

    rows = frappe.get_all(
        CONVERSATION_DOCTYPE,
        fields=["name"],
        order_by="modified desc",
        limit_page_length=500,
        ignore_permissions=True,
    )

    result = []

    for row in rows:
        doc = frappe.get_doc(CONVERSATION_DOCTYPE, row.get("name"))

        if not _current_user_can_see_conversation(doc):
            continue

        if not _conversation_matches_status(doc, status):
            continue

        result.append(_format_conversation(doc))

        if len(result) >= int(limit or 20):
            break

    return result


@frappe.whitelist()
def get_notification_detail(name):
    doc = ensure_notification_access(name)

    if doc.doctype == CONVERSATION_DOCTYPE:
        mark_notification_read(name)
        doc.reload()
        return _format_conversation(doc)

    return _format_notification_log(doc.as_dict())


@frappe.whitelist()
def mark_notification_read(name):
    doc = ensure_notification_access(name)

    if doc.doctype != CONVERSATION_DOCTYPE:
        if _field_exists(NOTIFICATION_DOCTYPE, "read"):
            frappe.db.set_value(NOTIFICATION_DOCTYPE, doc.name, "read", 1)
            frappe.db.commit()

        return {"ok": True}

    row = _get_recipient_row(doc, frappe.session.user)

    if row:
        row.read = 1
        row.read_on = now_datetime()
        doc.save(ignore_permissions=True)
        frappe.db.commit()

    return {"ok": True}


@frappe.whitelist()
def update_notification_status(name, status=None, read=None):
    doc = ensure_notification_access(name)

    if doc.doctype != CONVERSATION_DOCTYPE:
        if read is None:
            read = 1 if status == "Read" else 0

        if _field_exists(NOTIFICATION_DOCTYPE, "read"):
            frappe.db.set_value(NOTIFICATION_DOCTYPE, doc.name, "read", int(read))
            frappe.db.commit()

        return {"ok": True}

    if status in ["Open", "Waiting", "In Progress", "Done", "Archived"]:
        doc.status = status

    if read is not None:
        row = _get_recipient_row(doc, frappe.session.user)
        if row:
            row.read = int(read)
            row.read_on = now_datetime() if int(read) else None

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True}


@frappe.whitelist()
def reply_to_notification(name=None, message=None):
    ensure_logged_in()

    name = _coalesce_str("name", name)
    message = _coalesce_str("message", message)

    if not name:
        frappe.throw(_("Notification not found."))

    if not message:
        frappe.throw(_("Please enter a reply."))

    doc = ensure_notification_access(name)

    if doc.doctype != CONVERSATION_DOCTYPE:
        frappe.throw(_("Replies are only available on dashboard conversations."))

    doc.append("replies", {
        "reply_user": frappe.session.user,
        "reply_user_role": _get_current_role(),
        "message": message,
    })

    for row in doc.get("recipients") or []:
        if row.get("recipient_user") != frappe.session.user:
            row.read = 0
            row.read_on = None

    if doc.get("created_by_user") != frappe.session.user:
        pass

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "ok": True,
        "notification": _format_conversation(doc),
    }


@frappe.whitelist()
def get_dashboard_notification_summary():
    return get_notification_summary_for_page(limit=5)


def get_notification_summary_for_page(limit=5):
    ensure_logged_in()

    latest = get_notifications(status="All", limit=limit)

    unread_count = 0

    if _conversation_enabled():
        all_rows = get_notifications(status="All", limit=500)
        unread_count = sum(1 for row in all_rows if row.get("read_status") == "Unread")
    else:
        rows = frappe.get_all(
            NOTIFICATION_DOCTYPE,
            filters=_get_notification_log_filters(),
            fields=_notification_log_fields(),
            order_by="creation desc",
            limit_page_length=100,
        )
        unread_count = sum(1 for row in rows if not row.get("read"))

    return {
        "unread_count": unread_count,
        "latest": latest,
    }


@frappe.whitelist()
def get_notification_list_for_page(status="All", limit=20):
    return get_notifications(status=status, limit=limit)


@frappe.whitelist()
def send_dashboard_notification(
    recipient_users=None,
    notification_type="Message",
    message=None,
    priority="Normal",
    subject=None,
    title=None,
    linked_client=None,
    linked_event=None,
    reference_doctype=None,
    reference_name=None,
    requires_response=0,
    due_date=None,
):
    ensure_logged_in()

    if not _conversation_enabled():
        return _send_legacy_notification(
            recipient_users=recipient_users,
            notification_type=notification_type,
            message=message,
            priority=priority,
            subject=subject,
        )

    recipient_users = _normalise_recipient_users(_coalesce_raw("recipient_users", recipient_users))

    notification_type = _coalesce_str("notification_type", notification_type or "Message")
    message = _coalesce_str("message", message)
    priority = _coalesce_str("priority", priority or "Normal")
    title = _coalesce_str("title", title or subject or notification_type)
    linked_client = _coalesce_str("linked_client", linked_client)
    linked_event = _coalesce_str("linked_event", linked_event)
    reference_doctype = _coalesce_str("reference_doctype", reference_doctype)
    reference_name = _coalesce_str("reference_name", reference_name)
    due_date = _coalesce_raw("due_date", due_date)
    requires_response = _coalesce_raw("requires_response", requires_response)

    if not recipient_users:
        frappe.throw(_("Please select at least one recipient."))

    if not message:
        frappe.throw(_("Please enter a message."))

    allowed_users = _allowed_recipient_user_set()
    invalid_users = [user for user in recipient_users if user not in allowed_users]

    if invalid_users:
        frappe.throw(_("One or more selected recipients are not allowed."), frappe.PermissionError)

    doc = frappe.new_doc(CONVERSATION_DOCTYPE)
    doc.title = title or notification_type
    doc.conversation_type = notification_type
    doc.status = "Open"
    doc.priority = priority or "Normal"
    doc.message = message
    doc.created_by_user = frappe.session.user
    doc.created_by_role = _get_current_role()

    if _field_exists(CONVERSATION_DOCTYPE, "linked_client"):
        doc.linked_client = linked_client

    if _field_exists(CONVERSATION_DOCTYPE, "linked_event"):
        doc.linked_event = linked_event

    if _field_exists(CONVERSATION_DOCTYPE, "reference_doctype"):
        doc.reference_doctype = reference_doctype

    if _field_exists(CONVERSATION_DOCTYPE, "reference_name"):
        doc.reference_name = reference_name

    if _field_exists(CONVERSATION_DOCTYPE, "requires_response"):
        doc.requires_response = 1 if str(requires_response).lower() in ["1", "true", "yes", "on"] else 0

    if _field_exists(CONVERSATION_DOCTYPE, "due_date"):
        doc.due_date = due_date

    for recipient_user in recipient_users:
        if recipient_user == frappe.session.user:
            continue

        doc.append("recipients", {
            "recipient_user": recipient_user,
            "recipient_role": _get_recipient_role(recipient_user),
            "read": 0,
            "archived": 0,
            "muted": 0,
        })

    if not doc.get("recipients"):
        frappe.throw(_("Please select at least one recipient other than yourself."))

    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "ok": True,
        "message": "Notification sent.",
        "created": [doc.name],
        "name": doc.name,
    }


def _send_legacy_notification(
    recipient_users=None,
    notification_type="Dashboard Message",
    message=None,
    priority="Normal",
    subject=None,
):
    recipient_users = _normalise_recipient_users(recipient_users)

    if not recipient_users:
        frappe.throw(_("Please select at least one recipient."))

    if not message:
        frappe.throw(_("Please enter a message."))

    allowed_users = _allowed_recipient_user_set()
    invalid_users = [user for user in recipient_users if user not in allowed_users]

    if invalid_users:
        frappe.throw(_("One or more selected recipients are not allowed."), frappe.PermissionError)

    created = []

    for recipient_user in recipient_users:
        doc_data = {
            "doctype": NOTIFICATION_DOCTYPE,
            "subject": subject or notification_type,
            "email_content": message,
            "read": 0,
        }

        if _field_exists(NOTIFICATION_DOCTYPE, "for_user"):
            doc_data["for_user"] = recipient_user

        if _field_exists(NOTIFICATION_DOCTYPE, "from_user"):
            doc_data["from_user"] = frappe.session.user

        if _field_exists(NOTIFICATION_DOCTYPE, "type"):
            doc_data["type"] = notification_type

        if _field_exists(NOTIFICATION_DOCTYPE, "priority"):
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
    Used by other backend processes.

    Creates a Dashboard Conversation when available.
    Falls back to Notification Log if the new DocType is not installed.
    """
    if not recipient_user:
        return None

    if _conversation_enabled():
        doc = frappe.new_doc(CONVERSATION_DOCTYPE)
        doc.title = notification_type or "Dashboard Notification"
        doc.conversation_type = notification_type or "Message"
        doc.status = "Open"
        doc.priority = priority or "Normal"
        doc.message = message or ""
        doc.created_by_user = frappe.session.user if frappe.session.user != "Guest" else "Administrator"
        doc.created_by_role = _get_current_role() if frappe.session.user != "Guest" else "Admin"

        if _field_exists(CONVERSATION_DOCTYPE, "linked_client"):
            doc.linked_client = client or (reference_name if reference_doctype == "Client" else "")

        if _field_exists(CONVERSATION_DOCTYPE, "linked_event"):
            doc.linked_event = event or (reference_name if reference_doctype == "Event" else "")

        if _field_exists(CONVERSATION_DOCTYPE, "reference_doctype"):
            doc.reference_doctype = reference_doctype

        if _field_exists(CONVERSATION_DOCTYPE, "reference_name"):
            doc.reference_name = reference_name

        doc.append("recipients", {
            "recipient_user": recipient_user,
            "recipient_role": _get_recipient_role(recipient_user),
            "read": 0,
            "archived": 0,
            "muted": 0,
        })

        doc.insert(ignore_permissions=True)
        return doc.name

    doc_data = {
        "doctype": NOTIFICATION_DOCTYPE,
        "subject": notification_type or "Dashboard Notification",
        "email_content": message or "",
        "read": 0,
    }

    if _field_exists(NOTIFICATION_DOCTYPE, "for_user"):
        doc_data["for_user"] = recipient_user

    if _field_exists(NOTIFICATION_DOCTYPE, "from_user"):
        doc_data["from_user"] = frappe.session.user

    if _field_exists(NOTIFICATION_DOCTYPE, "type"):
        doc_data["type"] = notification_type

    if _field_exists(NOTIFICATION_DOCTYPE, "priority"):
        doc_data["priority"] = priority

    if _field_exists(NOTIFICATION_DOCTYPE, "document_type") and reference_doctype:
        doc_data["document_type"] = reference_doctype

    if _field_exists(NOTIFICATION_DOCTYPE, "document_name") and reference_name:
        doc_data["document_name"] = reference_name

    doc = frappe.get_doc(doc_data)
    doc.insert(ignore_permissions=True)

    return doc.name
