import frappe
from frappe import _
from dashboard.api.shared.clients import normalize_client_row


def get_franchisor_display_name():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    return frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user


def get_my_coach_name():
    if not frappe.db.exists("DocType", "Coach"):
        return ""

    candidate_fields = ["user", "coach_user", "linked_user", "email", "coach_email", "user_id"]

    for fieldname in candidate_fields:
        if not frappe.db.has_column("Coach", fieldname):
            continue

        coach = frappe.db.get_value(
            "Coach",
            {fieldname: frappe.session.user},
            ["name", "coach_name"],
            as_dict=True,
        )

        if coach:
            return coach.get("name") or ""

    return ""


@frappe.whitelist()
def get_clients():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    my_coach = get_my_coach_name()

    clients = frappe.get_all(
        "Client",
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
            "session_worker",
        ],
        order_by="full_name asc",
        limit_page_length=1000,
    )

    rows = []
    for client in clients:
        row = normalize_client_row(client)
        row["scope"] = "My" if my_coach and row.get("primary_coach") == my_coach else "All"
        rows.append(row)

    return rows


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
