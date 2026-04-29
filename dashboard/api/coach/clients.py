import frappe
from frappe import _
from dashboard.api.shared.clients import normalize_client_row


COACH_DOCTYPE = "Coach"
CLIENT_DOCTYPE = "Client"


def require_logged_in_user():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    return frappe.session.user


def get_coach_record(user=None):
    user = user or frappe.session.user

    if not frappe.db.exists("DocType", COACH_DOCTYPE):
        return None

    candidate_fields = [
        "user",
        "coach_user",
        "linked_user",
        "email",
        "coach_email",
        "user_id",
    ]

    for fieldname in candidate_fields:
        if not frappe.db.has_column(COACH_DOCTYPE, fieldname):
            continue

        coach = frappe.db.get_value(
            COACH_DOCTYPE,
            {fieldname: user},
            ["name", "coach_name"],
            as_dict=True,
        )

        if coach:
            return coach

    return None


def get_coach_display_name():
    require_logged_in_user()

    coach = get_coach_record()

    if coach:
        return coach.get("coach_name") or coach.get("name")

    return frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user


def get_current_coach_name():
    coach = get_coach_record()
    return coach.get("name") if coach else ""


def get_allowed_client_filters_for_coach():
    coach_name = get_current_coach_name()

    if not coach_name:
        return {"name": ["in", []]}

    client_meta = frappe.get_meta(CLIENT_DOCTYPE)

    or_filters = []

    if client_meta.has_field("primary_coach"):
        or_filters.append(["Client", "primary_coach", "=", coach_name])

    if client_meta.has_field("attending_coach"):
        or_filters.append(["Client", "attending_coach", "=", coach_name])

    if not or_filters:
        return {"name": ["in", []]}

    return or_filters


@frappe.whitelist()
def get_clients():
    require_logged_in_user()

    or_filters = get_allowed_client_filters_for_coach()

    clients = frappe.get_all(
        CLIENT_DOCTYPE,
        or_filters=or_filters if isinstance(or_filters, list) else None,
        filters=or_filters if isinstance(or_filters, dict) else None,
        fields=[
            "name",
            "name1",
            "last_name",
            "full_name",
            "preferred_name",
            "mobile",
            "email",
            "status",
            "client_type",
            "primary_coach",
            "attending_coach",
            "session_worker",
        ],
        order_by="full_name asc",
        limit_page_length=1000,
    )

    return [normalize_client_row(c) for c in clients]


def get_session_workers():
    if not frappe.db.exists("DocType", "Session Worker"):
        return []

    return frappe.get_all(
        "Session Worker",
        fields=["name"],
        order_by="name asc",
        limit_page_length=500,
    )


def get_client_types():
    if frappe.db.exists("DocType", "Client Type"):
        return frappe.get_all("Client Type", pluck="name", order_by="name asc")

    return ["Kid", "Teen", "Adult", "Uni Student", "School/Company"]
