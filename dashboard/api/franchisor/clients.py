import frappe
from frappe import _
from dashboard.api.shared.clients import normalize_client_row
from dashboard.api.coach.clients import get_coach_record


CLIENT_DOCTYPE = "Client"


def require_logged_in_user():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    return frappe.session.user


def get_franchisor_display_name():
    require_logged_in_user()
    return frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user


def get_my_coach_name():
    coach = get_coach_record()
    return coach.get("name") if coach else ""


def get_client_scope_filters(scope="my"):
    scope = (scope or "my").strip()

    if scope.lower() == "all":
        return {}

    if scope.lower() == "my":
        coach_name = get_my_coach_name()
    else:
        coach_name = scope

    if not coach_name:
        return {"name": ["in", []]}

    meta = frappe.get_meta(CLIENT_DOCTYPE)

    if meta.has_field("primary_coach"):
        return {"primary_coach": coach_name}

    return {"name": ["in", []]}


@frappe.whitelist()
def get_clients(scope="my"):
    require_logged_in_user()

    rows = frappe.get_all(
        CLIENT_DOCTYPE,
        filters=get_client_scope_filters(scope),
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
        limit_page_length=5000,
    )

    result = []

    for row in rows:
        item = normalize_client_row(row)
        item["scope"] = item.get("primary_coach") or "All"
        result.append(item)

    return result


def get_session_workers():
    if not frappe.db.exists("DocType", "Session Worker"):
        return []

    return frappe.get_all(
        "Session Worker",
        fields=["name"],
        order_by="name asc",
        limit_page_length=500,
    )


def get_coaches():
    if not frappe.db.exists("DocType", "Coach"):
        return []

    return frappe.get_all(
        "Coach",
        fields=["name", "coach_name"],
        order_by="coach_name asc",
        limit_page_length=500,
    )


def get_client_types():
    meta = frappe.get_meta(CLIENT_DOCTYPE)

    if meta.has_field("client_type"):
        df = meta.get_field("client_type")

        if df.fieldtype == "Select" and df.options:
            return [x.strip() for x in df.options.split("\n") if x.strip()]

    return ["Kid", "Teen", "Adult", "Uni Student", "School/Company"]
