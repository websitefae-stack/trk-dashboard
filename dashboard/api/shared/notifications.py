import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime, getdate, nowdate
from dashboard.api.shared.utils import get_label as _get_label, get_request_payload as _get_request_payload, coalesce_raw as _coalesce_raw, coalesce_str as _coalesce_str


CONVERSATION_DOCTYPE = "Dashboard Conversation"
MESSAGE_DOCTYPE = "Dashboard Conversation Message"
RECIPIENT_CHILD_DOCTYPE = "Dashboard Conversation Recipient"
REPLY_CHILD_DOCTYPE = "Dashboard Conversation Reply"

NOTIFICATION_DOCTYPE = "Notification Log"

FRANCHISOR_USERS = [
    "ashley@theresilientkid.co.uk",
    "hq@theresilientkid.co.uk",
    "office@theresilienthub.co.uk",
]


def ensure_logged_in():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def _conversation_enabled():
    return frappe.db.exists("DocType", CONVERSATION_DOCTYPE)


def _message_enabled():
    return frappe.db.exists("DocType", MESSAGE_DOCTYPE)


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


def _get_current_role():
    user = frappe.session.user

    if _is_franchisor_user(user):
        return "Franchisor"

    if _get_current_coach_name(user):
        return "Coach"

    if _get_current_session_worker_name(user):
        return "Session Worker"

    return "Admin"


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


def _get_client_meta():
    if not frappe.db.exists("DocType", "Client"):
        return None

    return frappe.get_meta("Client")


def _get_session_workers_linked_to_coach(coach_name):
    if not coach_name:
        return set()

    meta = _get_client_meta()
    if not meta or not meta.has_field("session_worker"):
        return set()

    worker_names = set()

    if meta.has_field("primary_coach"):
        worker_names.update(frappe.get_all(
            "Client",
            filters={"primary_coach": coach_name},
            pluck="session_worker",
            limit_page_length=5000,
            ignore_permissions=True,
        ))

    if meta.has_field("attending_coach"):
        worker_names.update(frappe.get_all(
            "Client",
            filters={"attending_coach": coach_name},
            pluck="session_worker",
            limit_page_length=5000,
            ignore_permissions=True,
        ))

    return {worker for worker in worker_names if worker}


def _get_coaches_linked_to_session_worker(worker_name):
    if not worker_name:
        return set()

    meta = _get_client_meta()
    if not meta or not meta.has_field("session_worker"):
        return set()

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

    coach_names = set()

    for row in rows:
        if row.get("primary_coach"):
            coach_names.add(row.get("primary_coach"))

        if row.get("attending_coach"):
            coach_names.add(row.get("attending_coach"))

    return coach_names


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
    ensure_logged_in()

    current_user = frappe.session.user
    current_role = _get_current_role()

    admins = _get_admin_recipients()
    admin_users = {row.get("recipient_user") for row in admins if row.get("recipient_user")}

    all_coaches = [
        row for row in _get_all_coaches()
        if row.get("recipient_user") not in admin_users
    ]
    coach_users = {row.get("recipient_user") for row in all_coaches if row.get("recipient_user")}

    all_session_workers = [
        row for row in _get_all_session_workers()
        if row.get("recipient_user") not in admin_users
        and row.get("recipient_user") not in coach_users
    ]

    coaches = []
    session_workers = []

    if current_role in ["Franchisor", "Admin"]:
        coaches = all_coaches
        session_workers = all_session_workers

    elif current_role == "Coach":
        coach_name = _get_current_coach_name(current_user)

        coaches = [
            row for row in all_coaches
            if row.get("recipient_user") != current_user
        ]

        linked_workers = _get_session_workers_linked_to_coach(coach_name)
        session_workers = [
            row for row in all_session_workers
            if row.get("source_name") in linked_workers
        ]

    elif current_role == "Session Worker":
        worker_name = _get_current_session_worker_name(current_user)
        linked_coaches = _get_coaches_linked_to_session_worker(worker_name)

        coaches = [
            row for row in all_coaches
            if row.get("source_name") in linked_coaches
        ]

        session_workers = []

    return {
        "admins": _dedupe_recipients(admins),
        "coaches": _dedupe_recipients(coaches),
        "session_workers": _dedupe_recipients(session_workers),
        "current_role": current_role,
    }


def _get_client_display_label(client_name):
    if not client_name or not frappe.db.exists("Client", client_name):
        return client_name or ""

    meta = frappe.get_meta("Client")
    fields = ["name"]

    for fieldname in ["full_name", "preferred_name", "name1", "first_name", "last_name"]:
        if meta.has_field(fieldname) and fieldname not in fields:
            fields.append(fieldname)

    row = frappe.db.get_value("Client", client_name, fields, as_dict=True) or {}

    for fieldname in ["full_name", "preferred_name"]:
        value = (row.get(fieldname) or "").strip()
        if value:
            return value

    first = (row.get("name1") or row.get("first_name") or "").strip()
    last = (row.get("last_name") or "").strip()

    return " ".join([part for part in [first, last] if part]).strip() or client_name


def _get_allowed_client_names_for_current_user():
    role = _get_current_role()

    if not frappe.db.exists("DocType", "Client"):
        return []

    meta = frappe.get_meta("Client")

    if role in ["Franchisor", "Admin"]:
        return frappe.get_all(
            "Client",
            pluck="name",
            limit_page_length=5000,
            ignore_permissions=True,
        )

    if role == "Coach":
        coach_name = _get_current_coach_name()
        if not coach_name:
            return []

        names = set()

        if meta.has_field("primary_coach"):
            names.update(frappe.get_all(
                "Client",
                filters={"primary_coach": coach_name},
                pluck="name",
                limit_page_length=5000,
                ignore_permissions=True,
            ))

        if meta.has_field("attending_coach"):
            names.update(frappe.get_all(
                "Client",
                filters={"attending_coach": coach_name},
                pluck="name",
                limit_page_length=5000,
                ignore_permissions=True,
            ))

        return sorted(names)

    if role == "Session Worker":
        worker_name = _get_current_session_worker_name()
        if not worker_name or not meta.has_field("session_worker"):
            return []

        return frappe.get_all(
            "Client",
            filters={"session_worker": worker_name},
            pluck="name",
            limit_page_length=5000,
            ignore_permissions=True,
        )

    return []


def _get_event_label(row):
    client_label = _get_client_display_label(row.get("custom_client")) if row.get("custom_client") else ""
    subject = row.get("subject") or "Session"

    starts_on = row.get("starts_on")
    date_text = ""

    if starts_on:
        try:
            date_text = starts_on.strftime("%d/%m/%Y %H:%M")
        except Exception:
            date_text = str(starts_on)

    parts = [part for part in [date_text, client_label or subject] if part]
    return " - ".join(parts) or row.get("name")


@frappe.whitelist()
def get_notification_link_options():
    ensure_logged_in()

    client_names = _get_allowed_client_names_for_current_user()

    clients = [
        {
            "value": client_name,
            "label": _get_client_display_label(client_name),
        }
        for client_name in client_names
    ]

    events = []

    if client_names and frappe.db.exists("DocType", "Event") and _field_exists("Event", "custom_client"):
        rows = frappe.get_all(
            "Event",
            fields=["name", "subject", "starts_on", "custom_client"],
            filters={"custom_client": ["in", client_names]},
            order_by="starts_on desc",
            limit_page_length=500,
            ignore_permissions=True,
        )

        events = [
            {
                "value": row.get("name"),
                "label": _get_event_label(row),
                "client": row.get("custom_client") or "",
                "custom_client": row.get("custom_client") or "",
            }
            for row in rows
        ]

    return {
        "clients": clients,
        "events": events,
    }


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


def _get_dashboard_base_url():
    role = _get_current_role()

    if role == "Coach":
        return "/coach_db"

    if role == "Session Worker":
        return "/session_worker_db"

    return "/franchisor_db"


def _get_reference_link(reference_doctype, reference_name, dashboard_base_url=""):
    if not reference_doctype or not reference_name:
        return ""

    if reference_doctype == "Client":
        return f"{dashboard_base_url}/client_details?name={reference_name}" if dashboard_base_url else ""

    if reference_doctype == "Event":
        return f"{dashboard_base_url}/calendar_details?event={reference_name}" if dashboard_base_url else ""

    return ""


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


def _create_conversation_message(
    conversation,
    message,
    message_type="Message",
    sent_by=None,
    role_type=None,
    is_internal=0,
    attachment=None,
):
    if not _message_enabled():
        return None

    if not conversation or not message:
        return None

    sent_by = sent_by or frappe.session.user
    role_type = role_type or _get_current_role()

    doc = frappe.new_doc(MESSAGE_DOCTYPE)
    doc.conversation = conversation
    doc.message_type = message_type or "Message"
    doc.message = message
    doc.sent_by = sent_by
    doc.sent_by_name = _get_user_full_name(sent_by)
    doc.role_type = role_type
    doc.created_on = now_datetime()
    doc.is_internal = 1 if int(is_internal or 0) else 0

    if attachment and _field_exists(MESSAGE_DOCTYPE, "attachment"):
        doc.attachment = attachment

    doc.insert(ignore_permissions=True)

    return doc.name


def _get_conversation_messages(conversation):
    if not conversation or not _message_enabled():
        return []

    fields = [
        "name",
        "conversation",
        "message_type",
        "message",
        "sent_by",
        "sent_by_name",
        "role_type",
        "created_on",
        "is_internal",
        "creation",
    ]

    if _field_exists(MESSAGE_DOCTYPE, "attachment"):
        fields.append("attachment")

    rows = frappe.get_all(
        MESSAGE_DOCTYPE,
        filters={"conversation": conversation},
        fields=fields,
        order_by="created_on asc, creation asc",
        limit_page_length=1000,
        ignore_permissions=True,
    )

    return [
        {
            "name": row.get("name"),
            "message_type": row.get("message_type") or "Message",
            "message": row.get("message") or "",
            "sent_by": row.get("sent_by") or "",
            "sent_by_label": row.get("sent_by_name") or _get_user_full_name(row.get("sent_by")),
            "sent_by_name": row.get("sent_by_name") or _get_user_full_name(row.get("sent_by")),
            "role_type": row.get("role_type") or "",
            "created_on": row.get("created_on") or row.get("creation"),
            "is_internal": int(row.get("is_internal") or 0),
            "attachment": row.get("attachment") or "",
            "idx": 0,
        }
        for row in rows
    ]


def _get_legacy_child_replies(doc):
    replies = []

    for row in doc.get("replies") or []:
        replies.append({
            "name": row.get("name"),
            "message_type": "Message",
            "message": row.get("message") or "",
            "sent_by": row.get("reply_user") or "",
            "sent_by_label": _get_user_full_name(row.get("reply_user")),
            "sent_by_name": _get_user_full_name(row.get("reply_user")),
            "role_type": row.get("reply_user_role") or "",
            "created_on": row.get("creation"),
            "is_internal": 0,
            "attachment": "",
            "idx": row.get("idx") or 0,
        })

    return replies


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

        is_recipient = doc.get("for_user") == frappe.session.user
        is_sender = doc.get("from_user") and doc.get("from_user") == frappe.session.user

        if (
            _field_exists(NOTIFICATION_DOCTYPE, "for_user")
            and doc.get("for_user")
            and not is_recipient
            and not is_sender
            and not _is_franchisor_user()
        ):
            frappe.throw(_("You do not have permission to access this notification."), frappe.PermissionError)

        return doc

    frappe.throw(_("Notification not found."))

def ensure_notification_access_for_user(notification_name, user):
    ensure_logged_in()

    user = (user or "").strip()

    if not notification_name:
        frappe.throw(_("Notification not found."))

    if not user:
        frappe.throw(_("User not found."), frappe.PermissionError)

    if _conversation_enabled() and frappe.db.exists(CONVERSATION_DOCTYPE, notification_name):
        doc = frappe.get_doc(CONVERSATION_DOCTYPE, notification_name)

        if doc.get("created_by_user") == user:
            return doc

        if _user_is_recipient(doc, user):
            return doc

        if _is_franchisor_user(user):
            return doc

        frappe.throw(_("You do not have permission to access this notification."), frappe.PermissionError)

    if frappe.db.exists(NOTIFICATION_DOCTYPE, notification_name):
        doc = frappe.get_doc(NOTIFICATION_DOCTYPE, notification_name)

        is_recipient = doc.get("for_user") == user
        is_sender = doc.get("from_user") and doc.get("from_user") == user

        if (
            _field_exists(NOTIFICATION_DOCTYPE, "for_user")
            and doc.get("for_user")
            and not is_recipient
            and not is_sender
            and not _is_franchisor_user(user)
        ):
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

    messages = _get_conversation_messages(doc.name)

    # Oldest first - the post, then its comments in the order they were
    # written, same as _format_notification_log_replies() below already
    # does for the legacy path. (Previously newest-first, which read
    # backwards for a "post + comments" feed and made the original message
    # look like just another reply at the bottom.)
    messages = sorted(messages, key=lambda row: row.get("created_on") or "")

    if not messages:
        messages = [{
            "name": doc.name + "-original",
            "message_type": "Message",
            "message": doc.get("message") or "",
            "sent_by": doc.get("created_by_user") or "",
            "sent_by_label": _get_user_full_name(doc.get("created_by_user") or ""),
            "sent_by_name": _get_user_full_name(doc.get("created_by_user") or ""),
            "role_type": doc.get("created_by_role") or "",
            "created_on": doc.get("creation"),
            "is_internal": 0,
            "attachment": "",
            "idx": 0,
        }]

    legacy_replies = _get_legacy_child_replies(doc)
    if legacy_replies:
        messages.extend(legacy_replies)
        messages.sort(key=lambda row: row.get("created_on") or "")

    status = doc.get("status") or "Open"
    can_archive = (
        (doc.get("created_by_user") == frappe.session.user or _is_franchisor_user())
        and status != "Archived"
    )

    created_by = doc.get("created_by_user") or ""
    is_sent_by_me = 1 if created_by and created_by == current_user else 0
    has_reply_from_other = any(
        (message.get("sent_by") or "") and (message.get("sent_by") or "") != created_by
        for message in messages
    )
    awaiting_response = 1 if (
        is_sent_by_me
        and int(doc.get("requires_response") or 0)
        and not has_reply_from_other
        and status != "Archived"
    ) else 0

    return {
        "name": doc.get("name"),
        "notification_type": doc.get("conversation_type") or "Message",
        "conversation_type": doc.get("conversation_type") or "Message",
        "title": doc.get("title") or doc.get("conversation_type") or "Notification",
        "message": doc.get("message") or "",
        "status": status,
        "read_status": "Read" if is_read else "Unread",
        "priority": doc.get("priority") or "Normal",
        "notification_date": doc.get("creation"),
        "modified": doc.get("modified"),
        "created_by_user": doc.get("created_by_user") or "",
        "created_by_label": _get_user_full_name(doc.get("created_by_user") or ""),
        "created_by_role": doc.get("created_by_role") or "",
        "is_sent_by_me": is_sent_by_me,
        "awaiting_response": awaiting_response,
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
        "reply_count": max(len(messages) - 1, 0),
        "message_count": len(messages),
        "messages": messages,
        "replies": messages,
        "is_archived": 1 if status == "Archived" else 0,
        "can_archive": 1 if can_archive else 0,
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
    }


def _format_notification_log_replies(row):
    replies = row.get("custom_replies") or []

    messages = [{
        "name": row.get("name") + "-original",
        "message_type": "Message",
        "message": row.get("email_content") or row.get("subject") or "",
        "sent_by": row.get("from_user") or "",
        "sent_by_label": _get_user_full_name(row.get("from_user")) if row.get("from_user") else "System",
        "sent_by_name": _get_user_full_name(row.get("from_user")) if row.get("from_user") else "System",
        "role_type": "",
        "created_on": row.get("creation"),
        "is_internal": 0,
        "attachment": "",
        "idx": 0,
    }]

    for reply in replies:
        reply = reply if isinstance(reply, dict) else reply.as_dict()
        messages.append({
            "name": reply.get("name"),
            "message_type": "Message",
            "message": reply.get("message") or "",
            "sent_by": reply.get("sent_by") or "",
            "sent_by_label": reply.get("sent_by_label") or _get_user_full_name(reply.get("sent_by")),
            "sent_by_name": reply.get("sent_by_label") or _get_user_full_name(reply.get("sent_by")),
            "role_type": "",
            "created_on": reply.get("sent_on"),
            "is_internal": 0,
            "attachment": reply.get("attachment") or "",
            "idx": reply.get("idx") or 0,
        })

    messages.sort(key=lambda item: str(item.get("created_on") or ""))

    return messages


def _format_notification_log(row):
    read_value = row.get("read")
    archived = int(row.get("custom_archived") or 0)
    due_date = row.get("custom_due_date")
    messages = _format_notification_log_replies(row)

    from_user = row.get("from_user") or ""
    is_sent_by_me = 1 if from_user and from_user == frappe.session.user else 0
    # There's no explicit "requires response" flag on a plain Notification
    # Log entry the way there is on a Dashboard Conversation - if the
    # current user sent it and nobody else has replied in the thread yet,
    # treat it as still awaiting a response.
    has_reply_from_other = any(
        (message.get("sent_by") or "") and (message.get("sent_by") or "") != from_user
        for message in messages
    )
    awaiting_response = 1 if (is_sent_by_me and not has_reply_from_other and not archived) else 0

    return {
        "name": row.get("name"),
        "notification_type": row.get("subject") or row.get("type") or "Notification",
        "conversation_type": row.get("type") or "Notification",
        "title": row.get("subject") or row.get("type") or "Notification",
        "message": row.get("email_content") or row.get("subject") or "",
        # Raw workflow status - matches _format_conversation()'s shape so
        # the Kanban board on the frontend can bucket rows from either
        # source (New / In Progress / Past Due / Archived) the same way,
        # purely from status + due_date + read_status.
        "status": "Archived" if archived else "Open",
        "read_status": "Unread" if not read_value else "Read",
        "priority": row.get("priority") or "Normal",
        "notification_date": row.get("creation"),
        "modified": row.get("modified") or row.get("creation"),
        "due_date": str(due_date) if due_date else "",
        "is_archived": archived,
        "can_archive": 1,
        "client": row.get("document_name") if row.get("document_type") == "Client" else "",
        "coach": "",
        "session_worker": "",
        "event": row.get("document_name") if row.get("document_type") == "Event" else "",
        "client_package": "",
        "client_package_balance": "",
        "reference_doctype": row.get("document_type") or "",
        "reference_name": row.get("document_name") or "",
        "sent_from": row.get("from_user") or "",
        "is_sent_by_me": is_sent_by_me,
        "awaiting_response": awaiting_response,
        "reply_count": max(len(messages) - 1, 0),
        "message_count": len(messages),
        "messages": messages,
        "recipients": _notification_log_thread_recipients(row),
        "replies": messages,
    }


def _notification_log_thread_recipients(row):
    thread_id = row.get("custom_thread_id")
    if not thread_id or not _field_exists(NOTIFICATION_DOCTYPE, "custom_thread_id"):
        return []

    sibling_rows = frappe.get_all(
        NOTIFICATION_DOCTYPE,
        filters={"custom_thread_id": thread_id},
        fields=["for_user", "read"],
        ignore_permissions=True,
    )

    return [
        {
            "recipient_user": sibling.get("for_user"),
            "recipient_label": _get_user_full_name(sibling.get("for_user")),
            "read": int(sibling.get("read") or 0),
            "read_on": None,
            "archived": 0,
        }
        for sibling in sibling_rows
        if sibling.get("for_user")
    ]


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
        "custom_due_date",
        "custom_archived",
        "custom_thread_id",
    ]

    for fieldname in optional_fields:
        if _field_exists(NOTIFICATION_DOCTYPE, fieldname):
            fields.append(fieldname)

    return fields


def _get_notification_log_filters(status=None):
    filters = {}

    if status and status != "All":
        if status == "Unread" and _field_exists(NOTIFICATION_DOCTYPE, "read"):
            filters["read"] = 0
        elif status == "Read" and _field_exists(NOTIFICATION_DOCTYPE, "read"):
            filters["read"] = 1

    return filters


def _get_notification_log_or_filters():
    # Visible to whichever side of the exchange the current user is on -
    # the person a notification was sent to, and (since replies are now
    # possible) the person who sent it too, so they can see it in their own
    # list rather than only being able to reach it by a direct link.
    or_filters = []

    if _field_exists(NOTIFICATION_DOCTYPE, "for_user"):
        or_filters.append(["for_user", "=", frappe.session.user])

    if _field_exists(NOTIFICATION_DOCTYPE, "from_user"):
        or_filters.append(["from_user", "=", frappe.session.user])

    return or_filters


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


def _get_session_worker_user_from_docname(worker_name):
    if not worker_name or not frappe.db.exists("Session Worker", worker_name):
        return ""

    meta = frappe.get_meta("Session Worker")

    for fieldname in ["user", "user_id", "email", "session_worker_email", "sw_email"]:
        if meta.has_field(fieldname):
            value = frappe.db.get_value("Session Worker", worker_name, fieldname)
            if value:
                return value

    return ""


def _get_coach_user_from_docname(coach_name):
    if not coach_name or not frappe.db.exists("Coach", coach_name):
        return ""

    meta = frappe.get_meta("Coach")

    for fieldname in ["user", "user_id", "email", "coach_email"]:
        if meta.has_field(fieldname):
            value = frappe.db.get_value("Coach", coach_name, fieldname)
            if value:
                return value

    return ""


def get_notifications_for_user(user, status="All", limit=20):
    original_user = frappe.session.user

    try:
        frappe.session.user = user
        return get_notifications(status=status, limit=limit)
    finally:
        frappe.session.user = original_user


def get_notification_summary_for_user(user, limit=5):
    notifications = get_notifications_for_user(user=user, status="All", limit=500)

    unread_count = 0
    open_count = 0

    for row in notifications:
        if row.get("read_status") == "Unread":
            unread_count += 1

        if row.get("status") not in ["Done", "Archived", "Closed"]:
            open_count += 1

    return {
        "unread_count": unread_count,
        "open_count": open_count,
        "latest": notifications[:int(limit or 5)],
    }


def get_notification_list_for_session_worker_doc(worker_name, status="All", limit=200):
    user = _get_session_worker_user_from_docname(worker_name)

    if not user:
        return []

    return get_notifications_for_user(user=user, status=status, limit=limit)


def get_notification_summary_for_session_worker_doc(worker_name, limit=5):
    user = _get_session_worker_user_from_docname(worker_name)

    if not user:
        return {
            "unread_count": 0,
            "open_count": 0,
            "latest": [],
        }

    return get_notification_summary_for_user(user=user, limit=limit)


def _dedupe_notification_log_rows_by_thread(rows):
    """
    Rows sharing a custom_thread_id (see _send_legacy_notification) are all
    copies of the same "sent to several people" notification - collapses
    them into one card per thread instead of one per recipient. Keeps
    whichever row belongs to the current viewer (correct personal read
    status) if they have one in the group, else the most recently created
    row in it. Rows with no thread_id (single-recipient notifications,
    system alerts, anything predating this field) pass through untouched.
    """
    current_user = frappe.session.user
    by_thread = {}
    singles = []

    for row in rows:
        thread_id = row.get("custom_thread_id")
        if not thread_id:
            singles.append(row)
            continue

        existing = by_thread.get(thread_id)
        if not existing:
            by_thread[thread_id] = row
            continue

        if existing.get("for_user") == current_user:
            continue

        if row.get("for_user") == current_user:
            by_thread[thread_id] = row
        elif str(row.get("creation") or "") > str(existing.get("creation") or ""):
            by_thread[thread_id] = row

    return singles + list(by_thread.values())


@frappe.whitelist()
def get_notifications(status="All", limit=20):
    ensure_logged_in()

    limit = int(limit or 20)
    result = []

    if _conversation_enabled():
        conversation_rows = frappe.get_all(
            CONVERSATION_DOCTYPE,
            fields=["name"],
            order_by="modified desc",
            limit_page_length=500,
            ignore_permissions=True,
        )

        for row in conversation_rows:
            doc = frappe.get_doc(CONVERSATION_DOCTYPE, row.get("name"))

            if not _current_user_can_see_conversation(doc):
                continue

            if not _conversation_matches_status(doc, status):
                continue

            result.append(_format_conversation(doc))

    # Notification Log rows are read regardless of whether "Dashboard
    # Conversation" is installed - some notifications (e.g. the calendar
    # sync app's own alerts) are written straight to Notification Log and
    # never go through the conversation system at all, so relying on
    # _conversation_enabled() alone would make those permanently invisible
    # here even though they exist and are perfectly reachable by name.
    or_filters = _get_notification_log_or_filters()

    if or_filters:
        log_rows = frappe.get_all(
            NOTIFICATION_DOCTYPE,
            fields=_notification_log_fields(),
            filters=_get_notification_log_filters(status),
            or_filters=or_filters,
            order_by="creation desc",
            limit_page_length=500,
            ignore_permissions=True,
        )

        log_rows = _dedupe_notification_log_rows_by_thread(log_rows)
        result.extend(_format_notification_log(row) for row in log_rows)

    response_needed = [
        row for row in result
        if int(row.get("requires_response") or 0)
        and row.get("due_date")
        and row.get("status") != "Archived"
    ]

    unread = [
        row for row in result
        if row.get("read_status") == "Unread"
        and row.get("status") != "Archived"
        and row not in response_needed
    ]

    open_rows = [
        row for row in result
        if row.get("status") != "Archived"
        and row not in response_needed
        and row not in unread
    ]

    archived = [
        row for row in result
        if row.get("status") == "Archived"
    ]

    response_needed.sort(key=lambda row: str(row.get("due_date") or ""))
    unread.sort(key=lambda row: str(row.get("modified") or row.get("notification_date") or ""), reverse=True)
    open_rows.sort(key=lambda row: str(row.get("modified") or row.get("notification_date") or ""), reverse=True)
    archived.sort(key=lambda row: str(row.get("modified") or row.get("notification_date") or ""), reverse=True)

    result = response_needed + unread + open_rows + archived

    return result[:limit]


def _format_conversation_for_user(doc, user):
    original_user = frappe.session.user

    try:
        frappe.session.user = user
        return _format_conversation(doc)
    finally:
        frappe.session.user = original_user


@frappe.whitelist()
def get_notification_detail(name=None, view_as=None, viewer=None):
    ensure_logged_in()

    name = _coalesce_str("name", name)
    view_as = _coalesce_str("view_as", view_as)
    viewer = _coalesce_str("viewer", viewer)

    if not name:
        frappe.throw(_("Notification not found."))

    if view_as and viewer == "franchisor":
        if frappe.db.exists("Coach", view_as):
            from dashboard.api.shared.coach_view_mode import get_coach_view_mode

            view_mode = get_coach_view_mode(
                scope=viewer,
                coach_name=view_as,
            )

            if not view_mode.get("is_view_mode"):
                frappe.throw(_("You do not have permission to view this coach."), frappe.PermissionError)

            view_user = _get_coach_user_from_docname(
                view_mode.get("view_coach_name")
            )

            if not view_user:
                frappe.throw(_("Coach user not found."), frappe.PermissionError)

            doc = ensure_notification_access_for_user(name, view_user)

            if doc.doctype == CONVERSATION_DOCTYPE:
                return _format_conversation_for_user(doc, view_user)

            return _format_notification_log(doc.as_dict())

        if frappe.db.exists("Session Worker", view_as):
            from dashboard.api.shared.session_worker_view_mode import get_session_worker_view_mode

            view_mode = get_session_worker_view_mode(
                scope=viewer,
                worker_name=view_as,
            )

            if not view_mode.get("is_view_mode"):
                frappe.throw(_("You do not have permission to view this session worker."), frappe.PermissionError)

            view_user = _get_session_worker_user_from_docname(
                view_mode.get("view_worker_name")
            )

            if not view_user:
                frappe.throw(_("Session worker user not found."), frappe.PermissionError)

            doc = ensure_notification_access_for_user(name, view_user)

            if doc.doctype == CONVERSATION_DOCTYPE:
                return _format_conversation_for_user(doc, view_user)

            return _format_notification_log(doc.as_dict())

    doc = ensure_notification_access(name)

    if doc.doctype == CONVERSATION_DOCTYPE:
        mark_notification_read(name)
        doc.reload()
        return _format_conversation(doc)

    if not doc.get("for_user") or doc.get("for_user") == frappe.session.user:
        mark_notification_read(name)
        doc.reload()

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
        frappe.db.set_value(row.doctype, row.name, {
            "read": 1,
            "read_on": now_datetime(),
        }, update_modified=False)
    else:
        doc.append("recipients", {
            "recipient_user": frappe.session.user,
            "recipient_role": _get_current_role(),
            "read": 1,
            "read_on": now_datetime(),
            "archived": 0,
            "muted": 0,
        })
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

    old_status = doc.get("status") or "Open"

    if status in ["Open", "Waiting", "In Progress", "Done", "Archived"]:
        doc.status = status

    if read is not None:
        row = _get_recipient_row(doc, frappe.session.user)

        if row:
            row.read = int(read)
            row.read_on = now_datetime() if int(read) else None

    doc.save(ignore_permissions=True)

    if status and status != old_status:
        _create_conversation_message(
            conversation=doc.name,
            message=f"Status changed from {old_status} to {status}.",
            message_type="Status Update",
            sent_by=frappe.session.user,
            role_type=_get_current_role(),
        )

    frappe.db.commit()

    return {"ok": True}


@frappe.whitelist()
def archive_notification(name=None):
    ensure_logged_in()

    name = _coalesce_str("name", name)

    if not name:
        frappe.throw(_("Notification not found."))

    doc = ensure_notification_access(name)

    if doc.doctype != CONVERSATION_DOCTYPE:
        if not _field_exists(NOTIFICATION_DOCTYPE, "custom_archived"):
            frappe.throw(_("Archiving isn't set up on this site yet."))

        frappe.db.set_value(NOTIFICATION_DOCTYPE, doc.name, "custom_archived", 1)
        frappe.db.commit()

        return {
            "ok": True,
            "notification": _format_notification_log(
                frappe.db.get_value(NOTIFICATION_DOCTYPE, doc.name, _notification_log_fields(), as_dict=True)
            ),
        }

    if doc.get("created_by_user") != frappe.session.user and not _is_franchisor_user():
        frappe.throw(_("Only the conversation author can archive this conversation."), frappe.PermissionError)

    doc.status = "Archived"
    doc.save(ignore_permissions=True)

    _create_conversation_message(
        conversation=doc.name,
        message="Conversation archived.",
        message_type="Status Update",
        sent_by=frappe.session.user,
        role_type=_get_current_role(),
    )

    frappe.db.commit()

    fresh_doc = frappe.get_doc(CONVERSATION_DOCTYPE, doc.name)

    return {
        "ok": True,
        "notification": _format_conversation(fresh_doc),
    }


@frappe.whitelist()
def unarchive_notification(name=None):
    ensure_logged_in()

    name = _coalesce_str("name", name)

    if not name:
        frappe.throw(_("Notification not found."))

    doc = ensure_notification_access(name)

    if doc.doctype != CONVERSATION_DOCTYPE:
        if not _field_exists(NOTIFICATION_DOCTYPE, "custom_archived"):
            frappe.throw(_("Archiving isn't set up on this site yet."))

        frappe.db.set_value(NOTIFICATION_DOCTYPE, doc.name, "custom_archived", 0)
        frappe.db.commit()

        return {
            "ok": True,
            "notification": _format_notification_log(
                frappe.db.get_value(NOTIFICATION_DOCTYPE, doc.name, _notification_log_fields(), as_dict=True)
            ),
        }

    if doc.get("created_by_user") != frappe.session.user and not _is_franchisor_user():
        frappe.throw(_("Only the conversation author can restore this conversation."), frappe.PermissionError)

    doc.status = "Open"
    doc.save(ignore_permissions=True)

    _create_conversation_message(
        conversation=doc.name,
        message="Conversation restored from archive.",
        message_type="Status Update",
        sent_by=frappe.session.user,
        role_type=_get_current_role(),
    )

    frappe.db.commit()

    fresh_doc = frappe.get_doc(CONVERSATION_DOCTYPE, doc.name)

    return {
        "ok": True,
        "notification": _format_conversation(fresh_doc),
    }


@frappe.whitelist()
def set_notification_due_date(name=None, due_date=None):
    """
    Moves a notification between New / In Progress / Past Due on the
    Kanban board by changing its due date (an empty due_date clears it
    back to New). Also un-archives it, since dragging a card out of the
    Archived column onto any of these implies it's active again.
    """
    ensure_logged_in()

    name = _coalesce_str("name", name)
    due_date = _coalesce_str("due_date", due_date)

    if not name:
        frappe.throw(_("Notification not found."))

    doc = ensure_notification_access(name)

    if doc.doctype != CONVERSATION_DOCTYPE:
        if not _field_exists(NOTIFICATION_DOCTYPE, "custom_due_date"):
            frappe.throw(_("Due dates aren't set up on this site yet."))

        updates = {"custom_due_date": due_date or None}

        if _field_exists(NOTIFICATION_DOCTYPE, "custom_archived"):
            updates["custom_archived"] = 0

        frappe.db.set_value(NOTIFICATION_DOCTYPE, doc.name, updates)
        frappe.db.commit()

        return {
            "ok": True,
            "notification": _format_notification_log(
                frappe.db.get_value(NOTIFICATION_DOCTYPE, doc.name, _notification_log_fields(), as_dict=True)
            ),
        }

    if doc.get("created_by_user") != frappe.session.user and not _is_franchisor_user():
        frappe.throw(_("Only the conversation author can change this notification's due date."), frappe.PermissionError)

    doc.due_date = due_date or None

    if doc.get("status") == "Archived":
        doc.status = "Open"

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    fresh_doc = frappe.get_doc(CONVERSATION_DOCTYPE, doc.name)

    return {
        "ok": True,
        "notification": _format_conversation(fresh_doc),
    }


def _reply_to_notification_log(doc, message, attachment):
    """
    Notification Log has no built-in thread/recipients structure - it's one
    row per (from_user, for_user) pair. A reply is appended to custom_replies
    (a Table Custom Field added by add_notification_log_reply_field.py) so
    it's kept with the original notification for either party to read back.

    Both parties already read the SAME row: get_notifications() matches on
    for_user == session.user OR from_user == session.user, so for_user and
    from_user both land on this one document already - there is no need to
    fabricate a second "Re:" notification for the other person, and doing
    so previously caused a new card to appear every time either side
    replied (stacking into "Re: Re: Re:" chains, with the card's preview
    showing the reply text instead of the original message). The reply is
    simply appended here and the row is marked unread so it resurfaces to
    whichever party hasn't seen it yet; mark_notification_read() flips it
    back the next time either of them opens it.

    If this notification was sent to several people at once, every sibling
    row shares the same custom_thread_id (see _send_legacy_notification) -
    the reply is mirrored onto every one of them so everyone in the group
    sees the same conversation update instead of just their own
    disconnected copy.
    """
    reply_row = {
        "message": message,
        "attachment": attachment or "",
        "sent_by": frappe.session.user,
        "sent_by_label": _get_user_full_name(frappe.session.user),
        "sent_on": now_datetime(),
    }

    doc.append("custom_replies", reply_row)
    doc.save(ignore_permissions=True)

    if _field_exists(NOTIFICATION_DOCTYPE, "read"):
        frappe.db.set_value(NOTIFICATION_DOCTYPE, doc.name, "read", 0, update_modified=False)

    thread_id = doc.get("custom_thread_id")

    if thread_id and _field_exists(NOTIFICATION_DOCTYPE, "custom_thread_id"):
        sibling_names = frappe.get_all(
            NOTIFICATION_DOCTYPE,
            filters={"custom_thread_id": thread_id, "name": ["!=", doc.name]},
            pluck="name",
            ignore_permissions=True,
        )

        for sibling_name in sibling_names:
            sibling_doc = frappe.get_doc(NOTIFICATION_DOCTYPE, sibling_name)
            sibling_doc.append("custom_replies", reply_row)
            sibling_doc.save(ignore_permissions=True)

            if _field_exists(NOTIFICATION_DOCTYPE, "read"):
                frappe.db.set_value(NOTIFICATION_DOCTYPE, sibling_name, "read", 0, update_modified=False)

    frappe.db.commit()

    fresh_doc = frappe.get_doc(NOTIFICATION_DOCTYPE, doc.name)

    return {
        "ok": True,
        "notification": _format_notification_log(fresh_doc.as_dict()),
    }


@frappe.whitelist()
def reply_to_notification(name=None, message=None, attachment=None):
    ensure_logged_in()

    name = _coalesce_str("name", name)
    message = _coalesce_str("message", message)
    attachment = _coalesce_str("attachment", attachment)

    if not name:
        frappe.throw(_("Notification not found."))

    if not message:
        frappe.throw(_("Please enter a reply."))

    doc = ensure_notification_access(name)

    if doc.doctype != CONVERSATION_DOCTYPE:
        return _reply_to_notification_log(doc, message, attachment)

    # Mark other recipients as unread using direct DB updates.
    # This avoids the "document has been modified" save conflict.
    recipient_users = {
        row.get("recipient_user")
        for row in doc.get("recipients") or []
        if row.get("recipient_user")
    }
    
    if doc.get("created_by_user") and doc.get("created_by_user") not in recipient_users:
        doc.append("recipients", {
            "recipient_user": doc.get("created_by_user"),
            "recipient_role": doc.get("created_by_role") or "Author",
            "read": 0 if doc.get("created_by_user") != frappe.session.user else 1,
            "read_on": None,
            "archived": 0,
            "muted": 0,
        })
        doc.save(ignore_permissions=True)
        doc.reload()
    
    for row in doc.get("recipients") or []:
        if row.get("recipient_user") != frappe.session.user:
            frappe.db.set_value(row.doctype, row.name, {
                "read": 0,
                "read_on": None,
            }, update_modified=False)
        else:
            frappe.db.set_value(row.doctype, row.name, {
                "read": 1,
                "read_on": now_datetime(),
            }, update_modified=False)

    _create_conversation_message(
        conversation=doc.name,
        message=message,
        message_type="Message",
        sent_by=frappe.session.user,
        role_type=_get_current_role(),
        attachment=attachment,
    )

    frappe.db.set_value(
        CONVERSATION_DOCTYPE,
        doc.name,
        "modified",
        now_datetime(),
        update_modified=False,
    )

    frappe.db.commit()

    fresh_doc = frappe.get_doc(CONVERSATION_DOCTYPE, doc.name)

    return {
        "ok": True,
        "notification": _format_conversation(fresh_doc),
    }


@frappe.whitelist()
def _kanban_bucket_for(row):
    """
    Same New / In Progress / Past Due / Archived bucketing the Notifications
    Kanban board uses on the frontend (see bucketFor() in notifications.js) -
    kept in sync so the sidebar badge counts the same thing the board shows.
    """
    if (row.get("status") or "Open") == "Archived":
        return "Archived"

    due_date = row.get("due_date")
    if not due_date:
        return "New"

    return "Past Due" if str(due_date) < nowdate() else "In Progress"


@frappe.whitelist()
def get_dashboard_notification_summary():
    ensure_logged_in()

    notifications = get_notifications(status="All", limit=500)

    unread_count = 0
    open_count = 0

    for row in notifications:
        bucket = _kanban_bucket_for(row)

        # The badge is meant to flag what actually needs attention - a
        # notification sitting in "In Progress" already has a future due
        # date and someone's on it, so it isn't counted here even if
        # nobody has opened it yet.
        if bucket in ["New", "Past Due"]:
            unread_count += 1

        if bucket != "Archived":
            open_count += 1

    latest = notifications[:5]

    return {
        "unread_count": unread_count,
        "open_count": open_count,
        "latest": latest,
    }

def get_notification_summary_for_page(limit=5):
    ensure_logged_in()

    summary = get_dashboard_notification_summary()

    latest = summary.get("latest") or []
    latest = latest[:int(limit or 5)]

    return {
        "unread_count": summary.get("unread_count", 0),
        "open_count": summary.get("open_count", 0),
        "latest": latest,
    }


@frappe.whitelist()
def get_notification_list_for_page(status="All", limit=20):
    return get_notifications(status=status, limit=limit)


def _find_recent_duplicate_conversation(title, message, notification_type, recipient_users):
    if not _conversation_enabled():
        return ""

    since = add_to_date(now_datetime(), seconds=-20)
    expected_recipients = set(recipient_users or [])

    rows = frappe.get_all(
        CONVERSATION_DOCTYPE,
        filters={
            "created_by_user": frappe.session.user,
            "title": title,
            "conversation_type": notification_type,
            "message": message,
            "creation": [">=", since],
        },
        fields=["name"],
        order_by="creation desc",
        limit_page_length=10,
        ignore_permissions=True,
    )

    for row in rows:
        doc = frappe.get_doc(CONVERSATION_DOCTYPE, row.get("name"))
        existing_recipients = {
            recipient.get("recipient_user")
            for recipient in doc.get("recipients") or []
            if recipient.get("recipient_user")
        }

        if existing_recipients == expected_recipients:
            return doc.name

    return ""


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
    attachment=None,
):
    
    ensure_logged_in()

    if not _conversation_enabled():
        return _send_legacy_notification(
            recipient_users=recipient_users,
            notification_type=notification_type,
            message=message,
            priority=priority,
            subject=subject,
            due_date=_coalesce_str("due_date", due_date),
            linked_client=_coalesce_str("linked_client", linked_client),
            linked_event=_coalesce_str("linked_event", linked_event),
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
    attachment = _coalesce_str("attachment", attachment)

    if not recipient_users:
        frappe.throw(_("Please select at least one recipient."))

    if not message:
        frappe.throw(_("Please enter a message."))

    allowed_users = _allowed_recipient_user_set()
    invalid_users = [user for user in recipient_users if user not in allowed_users]

    if invalid_users:
        frappe.throw(_("One or more selected recipients are not allowed."), frappe.PermissionError)

    duplicate_name = _find_recent_duplicate_conversation(
        title=title or notification_type,
        message=message,
        notification_type=notification_type,
        recipient_users=[
            user for user in recipient_users
            if user != frappe.session.user
        ],
    )
    
    if duplicate_name:
        return {
            "ok": True,
            "message": "Notification sent.",
            "created": [duplicate_name],
            "name": duplicate_name,
            "duplicate_prevented": 1,
        }
        
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

    doc.append("recipients", {
        "recipient_user": frappe.session.user,
        "recipient_role": _get_current_role(),
        "read": 1,
        "read_on": now_datetime(),
        "archived": 0,
        "muted": 0,
    })
    
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

    _create_conversation_message(
        conversation=doc.name,
        message=message,
        message_type="Message",
        sent_by=frappe.session.user,
        role_type=_get_current_role(),
        attachment=attachment,
    )
    
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
    due_date=None,
    linked_client=None,
    linked_event=None,
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

    # Notification Log's for_user is a single Link, so sending to several
    # people has always meant one row per recipient - stamping all of them
    # with the same thread_id is what lets get_notifications() collapse
    # them back into a single shared card, and replies get mirrored across
    # every row in the group (see _reply_to_notification_log). Only
    # meaningful with 2+ recipients, but harmless (and simpler) to always
    # set it.
    thread_id = frappe.generate_hash(length=12) if _field_exists(NOTIFICATION_DOCTYPE, "custom_thread_id") else None

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

        if thread_id:
            doc_data["custom_thread_id"] = thread_id

        # NOTE: deliberately not setting "type" here - Notification Log's
        # type field is Frappe's own internal classification (Mention/
        # Energy Point/Assignment/Share/Alert), not a freeform label. Our
        # custom notification_type values ("Task", "New Public Booking",
        # etc.) aren't in that list and raise a ValidationError if assigned
        # - the subject field above already carries the meaningful label.
        if _field_exists(NOTIFICATION_DOCTYPE, "priority"):
            doc_data["priority"] = priority

        # Frappe's own Notification Log.after_insert() unconditionally
        # builds a "view record" link from document_type/document_name
        # (get_url_to_form -> slug()), which crashes with
        # "'NoneType' object has no attribute 'lower'" if both are left
        # blank. Notification Log only has room for one such link, so a
        # linked client takes priority (that's what _format_notification_log()
        # reads to show "Linked Client" on the detail page - dropping it
        # here silently was why a coach's note about a client kept arriving
        # with no client attached, even though they'd picked one), then a
        # linked event, and only falls back to the recipient's own User
        # record when this notification has no specific record to link to.
        if linked_client and frappe.db.exists("Client", linked_client):
            link_doctype, link_name = "Client", linked_client
        elif linked_event and frappe.db.exists("Event", linked_event):
            link_doctype, link_name = "Event", linked_event
        else:
            link_doctype, link_name = "User", recipient_user

        if _field_exists(NOTIFICATION_DOCTYPE, "document_type"):
            doc_data["document_type"] = link_doctype

        if _field_exists(NOTIFICATION_DOCTYPE, "document_name"):
            doc_data["document_name"] = link_name

        # Drives the Notifications Kanban board (New / In Progress / Past
        # Due / Archived) - see _format_notification_log(). custom_due_date
        # is a Custom Field added by
        # patches/add_notification_log_kanban_fields.py.
        if due_date and _field_exists(NOTIFICATION_DOCTYPE, "custom_due_date"):
            doc_data["custom_due_date"] = due_date

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

        _create_conversation_message(
            conversation=doc.name,
            message=message or "",
            message_type="Message",
            sent_by=doc.created_by_user,
            role_type=doc.created_by_role,
        )

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

    # See the matching note in _send_legacy_notification() above - "type"
    # is Frappe's own fixed classification, not a freeform label.
    if _field_exists(NOTIFICATION_DOCTYPE, "priority"):
        doc_data["priority"] = priority

    # Same crash guard as _send_legacy_notification() above - Frappe's own
    # after_insert hook needs document_type/document_name to both be set
    # to something real, or get_url_to_form() throws building the email
    # link. Prefer an explicit reference, then fall back to the client/
    # event passed in directly (matching the conversation-enabled branch
    # above, which already honours client/event this way), and only fall
    # back to the recipient's own User record when none of those exist.
    if reference_doctype and reference_name:
        link_doctype, link_name = reference_doctype, reference_name
    elif client:
        link_doctype, link_name = "Client", client
    elif event:
        link_doctype, link_name = "Event", event
    else:
        link_doctype, link_name = "User", recipient_user

    if _field_exists(NOTIFICATION_DOCTYPE, "document_type"):
        doc_data["document_type"] = link_doctype

    if _field_exists(NOTIFICATION_DOCTYPE, "document_name"):
        doc_data["document_name"] = link_name

    doc = frappe.get_doc(doc_data)
    doc.insert(ignore_permissions=True)

    return doc.name
