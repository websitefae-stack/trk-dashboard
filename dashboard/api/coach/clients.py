import frappe
from frappe import _
from dashboard.api.shared.clients import normalize_client_row


def get_coach_display_name():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    if frappe.db.exists("DocType", "Coach"):
        candidate_fields = ["user", "coach_user", "linked_user", "email", "coach_email", "user_id"]

        for fieldname in candidate_fields:
            if not frappe.db.has_column("Coach", fieldname):
                continue

            coach = frappe.db.get_value(
                "Coach",
                {fieldname: frappe.session.user},
                ["coach_name", "name"],
                as_dict=True,
            )

            if coach:
                return coach.get("coach_name") or coach.get("name")

    return frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user


@frappe.whitelist()
def get_clients():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

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
        limit_page_length=500,
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
