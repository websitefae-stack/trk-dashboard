import frappe

from dashboard.api.shared.permissions import (
    CLIENT_DOCTYPE,
    COACH_DOCTYPE,
    SESSION_WORKER_DOCTYPE,
    ensure_office_user,
)


BASE_COACH_LIST_FIELDS = [
    "name",
    "coach_name",
    "user",
    "coach_email",
]


OPTIONAL_COACH_LIST_FIELDS = [
    "phone",
    "mobile",
    "cell_number",
]


def get_existing_fields(doctype, fields):
    meta = frappe.get_meta(doctype)

    return [
        fieldname
        for fieldname in fields
        if meta.has_field(fieldname)
    ]


def get_coach_display_name(coach):
    return (
        coach.get("coach_name")
        or coach.get("name")
        or "Unnamed Coach"
    )


def get_coach_mobile(coach):
    return (
        coach.get("mobile")
        or coach.get("phone")
        or coach.get("cell_number")
        or ""
    )


def get_client_count_for_coach(coach_name):
    if not coach_name:
        return 0

    client_meta = frappe.get_meta(CLIENT_DOCTYPE)
    or_filters = []

    if client_meta.has_field("primary_coach"):
        or_filters.append(["primary_coach", "=", coach_name])

    if client_meta.has_field("attending_coach"):
        or_filters.append(["attending_coach", "=", coach_name])

    if not or_filters:
        return 0

    client_names = frappe.get_all(
        CLIENT_DOCTYPE,
        or_filters=or_filters,
        pluck="name",
        limit_page_length=5000,
    )

    return len(set(client_names))


def get_session_worker_count_for_coach(coach_name):
    if not coach_name:
        return 0

    session_worker_meta = frappe.get_meta(SESSION_WORKER_DOCTYPE)

    possible_link_fields = [
        "coach",
        "primary_coach",
        "attending_coach",
    ]

    or_filters = []

    for fieldname in possible_link_fields:
        if session_worker_meta.has_field(fieldname):
            or_filters.append([fieldname, "=", coach_name])

    if not or_filters:
        return 0

    session_worker_names = frappe.get_all(
        SESSION_WORKER_DOCTYPE,
        or_filters=or_filters,
        pluck="name",
        limit_page_length=5000,
    )

    return len(set(session_worker_names))


def normalize_coach_row(coach):
    coach_name = coach.get("name")

    return {
        "name": coach_name,
        "coach_name": coach.get("coach_name") or "",
        "display_name": get_coach_display_name(coach),
        "user": coach.get("user") or "",
        "coach_email": coach.get("coach_email") or "",
        "mobile": get_coach_mobile(coach),
        "client_count": get_client_count_for_coach(coach_name),
        "session_worker_count": get_session_worker_count_for_coach(coach_name),
    }


@frappe.whitelist()
def get_coaches():
    ensure_office_user()

    fields = BASE_COACH_LIST_FIELDS + get_existing_fields(
        COACH_DOCTYPE,
        OPTIONAL_COACH_LIST_FIELDS,
    )

    coaches = frappe.get_all(
        COACH_DOCTYPE,
        fields=fields,
        filters=[
            ["user", "!=", frappe.session.user],
        ],
        order_by="coach_name asc",
        limit_page_length=5000,
    )

    return [normalize_coach_row(coach) for coach in coaches]
