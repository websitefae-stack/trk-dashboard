import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.contacts import (
    get_paginated_contacts_for_scope,
    get_current_coach_name,
)


def get_coaches():
    return frappe.get_all(
        "Coach",
        fields=["name", "coach_name"],
        order_by="coach_name asc",
    )


def get_session_workers():
    return frappe.get_all(
        "Session Worker",
        fields=["name"],
        order_by="name asc",
    )


def get_franchisor_display_name():
    return (
        frappe.db.get_value(
            "Coach",
            {"user": frappe.session.user},
            "coach_name",
        )
        or frappe.session.user
    )


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    contact_scope = frappe.form_dict.get("contact_scope") or "my"

    context.no_cache = 1
    context.page_title = "Contacts"
    context.active_page = "contacts"

    context.dashboard_user_name = get_franchisor_display_name()

    context.contact_scope = contact_scope

    context.my_coach_name = get_current_coach_name()

    context.my_coach_display_name = frappe.db.get_value(
        "Coach",
        context.my_coach_name,
        "coach_name",
    ) or "My contacts"

    context.coaches = get_coaches()

    context.session_workers = get_session_workers()

    contact_data = get_paginated_contacts_for_scope(
        "franchisor",
        show_all=False,
        coach_scope=contact_scope,
    )

    context.contacts = contact_data.get("contacts", [])
    context.pagination = contact_data.get("pagination", {})
    context.search = contact_data.get("search", "")
