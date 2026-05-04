import frappe
from frappe import _


DOCTYPE = "TRK Notification"
VALID_STATUSES = ["Unread", "Read", "Archived"]

SESSION_WORKER_DOCTYPE = "Session Worker"
COACH_DOCTYPE = "Coach"
CLIENT_DOCTYPE = "Client"

FRANCHISOR_USERS = {
    "ashley@theresilientkid.co.uk",
    "office@theresilientpeople.uk",
    "hq@theresilientkid.co.uk",
}


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
            "Notification recipient does not exist: {0}".format(recipient_user),
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


def _is_franchisor_user():
    return frappe.session.user in FRANCHISOR_USERS


def _get_current_session_worker():
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
        return None

    return frappe.get_doc(SESSION_WORKER_DOCTYPE, session_worker_name)


def _get_current_coach():
    coach_name = frappe.db.get_value(
        COACH_DOCTYPE,
        {"user": frappe.session.user},
        "name",
    )

    if not coach_name:
        coach_name = frappe.db.get_value(
            COACH_DOCTYPE,
            {"coach_email": frappe.session.user},
            "name",
        )

    if not coach_name:
        return None

    return frappe.get_doc(COACH_DOCTYPE, coach_name)


def _get_dashboard_type():
    if _is_franchisor_user():
        return "franchisor"

    if _get_current_session_worker():
        return "session_worker"

    if _get_current_coach():
        return "coach"

    return "unknown"


def _valid_user(user):
    return bool(user and frappe.db.exists("User", user))


def _recipient_row(label, recipient_user, recipient_type, reference_name):
    if not _valid_user(recipient_user):
        return None

    return {
        "label": label,
        "recipient_user": recipient_user,
        "recipient_type": recipient_type,
        "reference_name": reference_name,
    }


def _add_unique_recipient(recipients, seen_users, row):
    if not row:
        return

    user = row.get("recipient_user")

    if user in seen_users:
        return

    seen_users.add(user)
    recipients.append(row)


def _get_coach_user(coach):
    return coach.get("user") or coach.get("coach_email") or ""


def _get_session_worker_user(session_worker):
    return session_worker.get("user") or session_worker.get("sw_email") or ""


def _get_all_coach_recipients(exclude_coach_name=None):
    recipients = []
    seen_users = set()

    coaches = frappe.get_all(
        COACH_DOCTYPE,
        fields=["name", "coach_name", "user", "coach_email"],
        order_by="coach_name asc",
        limit_page_length=1000,
    )

    for coach in coaches:
        if exclude_coach_name and coach.name == exclude_coach_name:
            continue

        row = _recipient_row(
            label=coach.coach_name or coach.name,
            recipient_user=_get_coach_user(coach),
            recipient_type="Coach",
            reference_name=coach.name,
        )

        _add_unique_recipient(recipients, seen_users, row)

    return recipients


def _get_all_session_worker_recipients():
    recipients = []
    seen_users = set()

    session_workers = frappe.get_all(
        SESSION_WORKER_DOCTYPE,
        fields=["name", "sw_name", "user", "sw_email"],
        order_by="sw_name asc",
        limit_page_length=1000,
    )

    for session_worker in session_workers:
        row = _recipient_row(
            label=session_worker.sw_name or session_worker.name,
            recipient_user=_get_session_worker_user(session_worker),
            recipient_type="Session Worker",
            reference_name=session_worker.name,
        )

        _add_unique_recipient(recipients, seen_users, row)

    return recipients


def _get_sw_linked_coaches_from_session_worker(session_worker):
    recipients = []
    seen_users = set()

    for row in session_worker.get("linked_coaches") or []:
        if not row.get("is_active") or not row.get("coach"):
            continue

        coach = frappe.get_doc(COACH_DOCTYPE, row.coach)

        recipient = _recipient_row(
            label=coach.coach_name or coach.name,
            recipient_user=coach.user or coach.coach_email,
            recipient_type="Coach",
            reference_name=coach.name,
        )

        _add_unique_recipient(recipients, seen_users, recipient)

    return recipients


def _get_sw_linked_coaches_from_clients(session_worker):
    recipients = []
    seen_users = set()

    client_meta = frappe.get_meta(CLIENT_DOCTYPE)

    possible_sw_fields = [
        "session_worker",
        "session_worker_name",
        "linked_session_worker",
    ]

    possible_coach_fields = [
        "coach",
        "primary_coach",
        "attending_coach",
        "secondary_coach",
    ]

    client_filters = []

    for fieldname in possible_sw_fields:
        if client_meta.has_field(fieldname):
            client_filters.append({fieldname: session_worker.name})

    clients = []

    for filters in client_filters:
        clients.extend(
            frappe.get_all(
                CLIENT_DOCTYPE,
                filters=filters,
                fields=["name"],
                limit_page_length=1000,
            )
        )

    for client in clients:
        client_doc = frappe.get_doc(CLIENT_DOCTYPE, client.name)

        for coach_field in possible_coach_fields:
            if client_doc.meta.has_field(coach_field) and client_doc.get(coach_field):
                coach = frappe.get_doc(COACH_DOCTYPE, client_doc.get(coach_field))

                recipient = _recipient_row(
                    label=coach.coach_name or coach.name,
                    recipient_user=coach.user or coach.coach_email,
                    recipient_type="Coach",
                    reference_name=coach.name,
                )

                _add_unique_recipient(recipients, seen_users, recipient)

        for table_field in ["coaches", "linked_coaches", "attending_coaches"]:
            if not client_doc.meta.has_field(table_field):
                continue

            for row in client_doc.get(table_field) or []:
                coach_name = row.get("coach") or row.get("coach_name")
                if not coach_name:
                    continue

                if not frappe.db.exists(COACH_DOCTYPE, coach_name):
                    continue

                coach = frappe.get_doc(COACH_DOCTYPE, coach_name)

                recipient = _recipient_row(
                    label=coach.coach_name or coach.name,
                    recipient_user=coach.user or coach.coach_email,
                    recipient_type="Coach",
                    reference_name=coach.name,
                )

                _add_unique_recipient(recipients, seen_users, recipient)

    return recipients


def _get_coach_linked_session_workers(coach):
    recipients = []
    seen_users = set()

    session_workers = frappe.get_all(
        SESSION_WORKER_DOCTYPE,
        fields=["name", "sw_name", "user", "sw_email"],
        order_by="sw_name asc",
        limit_page_length=1000,
    )

    for session_worker in session_workers:
        sw_doc = frappe.get_doc(SESSION_WORKER_DOCTYPE, session_worker.name)

        is_linked = False
        for row in sw_doc.get("linked_coaches") or []:
            if row.get("is_active") and row.get("coach") == coach.name:
                is_linked = True
                break

        if not is_linked:
            continue

        recipient = _recipient_row(
            label=session_worker.sw_name or session_worker.name,
            recipient_user=session_worker.user or session_worker.sw_email,
            recipient_type="Session Worker",
            reference_name=session_worker.name,
        )

        _add_unique_recipient(recipients, seen_users, recipient)

    return recipients


@frappe.whitelist()
def get_notification_recipients():
    ensure_logged_in()

    dashboard_type = _get_dashboard_type()

    if dashboard_type == "session_worker":
        session_worker = _get_current_session_worker()

        recipients = []
        seen_users = set()

        for row in _get_sw_linked_coaches_from_session_worker(session_worker):
            _add_unique_recipient(recipients, seen_users, row)

        for row in _get_sw_linked_coaches_from_clients(session_worker):
            _add_unique_recipient(recipients, seen_users, row)

        return {
            "dashboard_type": "session_worker",
            "coaches": recipients,
            "session_workers": [],
            "franchisors": [],
        }

    if dashboard_type == "coach":
        coach = _get_current_coach()

        return {
            "dashboard_type": "coach",
            "coaches": _get_all_coach_recipients(exclude_coach_name=coach.name),
            "session_workers": _get_coach_linked_session_workers(coach),
            "franchisors": [],
        }

    if dashboard_type == "franchisor":
        franchisors = []
        seen_users = set()

        for user in FRANCHISOR_USERS:
            row = _recipient_row(
                label=frappe.get_cached_value("User", user, "full_name") or user,
                recipient_user=user,
                recipient_type="Franchisor",
                reference_name=user,
            )

            _add_unique_recipient(franchisors, seen_users, row)

        return {
            "dashboard_type": "franchisor",
            "coaches": _get_all_coach_recipients(),
            "session_workers": _get_all_session_worker_recipients(),
            "franchisors": franchisors,
        }

    frappe.throw(_("You are not allowed to send notifications."), frappe.PermissionError)


def _normalise_recipient_users(recipient_users):
    if isinstance(recipient_users, str):
        try:
            recipient_users = frappe.parse_json(recipient_users)
        except Exception:
            recipient_users = [recipient_users]

    if not isinstance(recipient_users, list):
        recipient_users = [recipient_users]

    cleaned = []

    for user in recipient_users:
        user = (user or "").strip()
        if user and user not in cleaned:
            cleaned.append(user)

    return cleaned


@frappe.whitelist()
def send_dashboard_notification(recipient_users=None, notification_type=None, message=None, priority="Normal"):
    ensure_logged_in()

    notification_type = (notification_type or "Dashboard Message").strip()
    message = (message or "").strip()
    priority = (priority or "Normal").strip()

    if not message:
        frappe.throw(_("Enter a message."))

    selected_users = _normalise_recipient_users(recipient_users)

    if not selected_users:
        frappe.throw(_("Select at least one recipient."))

    recipient_data = get_notification_recipients()
    dashboard_type = recipient_data.get("dashboard_type")

    allowed_rows = []
    allowed_rows.extend(recipient_data.get("coaches") or [])
    allowed_rows.extend(recipient_data.get("session_workers") or [])
    allowed_rows.extend(recipient_data.get("franchisors") or [])

    allowed_users = {row["recipient_user"]: row for row in allowed_rows}

    if dashboard_type == "session_worker" and len(selected_users) > 1:
        frappe.throw(_("Session Workers can send to one person at a time."))

    if dashboard_type == "coach":
        selected_types = [
            allowed_users.get(user, {}).get("recipient_type")
            for user in selected_users
        ]

        if "Coach" in selected_types and len(selected_users) > 1:
            frappe.throw(_("Coach-to-coach notifications must be sent one at a time."))

    created = []

    for recipient_user in selected_users:
        if recipient_user not in allowed_users:
            frappe.throw(_("You are not allowed to notify: {0}").format(recipient_user))

        row = allowed_users[recipient_user]

        created_name = create_trk_notification(
            recipient_user=recipient_user,
            notification_type=notification_type,
            message=message,
            priority=priority,
            reference_doctype=row.get("recipient_type"),
            reference_name=row.get("reference_name"),
            coach=row.get("reference_name") if row.get("recipient_type") == "Coach" else None,
            session_worker=row.get("reference_name") if row.get("recipient_type") == "Session Worker" else None,
            sent_from=frappe.session.user,
        )

        if created_name:
            created.append(created_name)

    frappe.db.commit()

    return {
        "ok": 1,
        "created": created,
        "message": _("{0} notification(s) sent.").format(len(created)),
    }


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
