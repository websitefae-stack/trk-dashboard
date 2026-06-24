import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.contacts import (
    get_contacts_for_scope,
    get_paginated_contacts_for_scope,
    get_current_coach_name,
    get_contact_names_from_clients,
    get_linked_clients_for_contact,
    get_contact_display_name,
    dedupe_contacts_prefer_customer,
)
from dashboard.api.shared.coach_view_mode import get_coach_view_mode


CLIENT_FIELDS = [
    "name",
    "full_name",
    "name1",
    "last_name",
    "status",
    "client_type",
    "primary_coach",
    "attending_coach",
    "session_worker",
    "billing_contact",
]


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    view_as = frappe.form_dict.get("view_as")
    viewer = frappe.form_dict.get("viewer")

    view_mode = get_coach_view_mode(
        scope=viewer,
        coach_name=view_as,
    )

    context.no_cache = 1
    context.page_title = "Contacts"
    context.active_page = "contacts"
    context.dashboard_notifications_url = "/coach_db/notifications" + (view_mode.get("query_string") or "")
    context.dashboard_base_url = "/coach_db"

    context.coach_view_mode = view_mode
    context.coach_view_query = view_mode.get("query_string") or ""
    context.coach_is_view_mode = view_mode.get("is_view_mode") or 0
    context.coach_view_return_to = view_mode.get("return_to") or ""
    context.coach_view_display_name = view_mode.get("view_coach_display_name") or ""

    if context.coach_is_view_mode:
        context.dashboard_user_name = context.coach_view_display_name
        context.contacts = get_contacts_for_view_coach(view_mode.get("view_coach_name"))
    else:
        redirect_if_wrong_dashboard("coach")

        context.dashboard_user_name = frappe.db.get_value(
            "Coach",
            get_current_coach_name(),
            "coach_name",
        ) or frappe.session.user

        contact_data = get_paginated_contacts_for_scope("coach")
        context.contacts = contact_data.get("contacts", [])
        context.pagination = contact_data.get("pagination", {})
        context.search = contact_data.get("search", "")


def get_clients_for_view_coach(coach_name):
    coach_name = (coach_name or "").strip()

    if not coach_name:
        return []

    rows_by_name = {}

    for row in frappe.get_all(
        "Client",
        filters={"primary_coach": coach_name},
        fields=CLIENT_FIELDS,
        order_by="full_name asc, name1 asc, last_name asc",
        limit_page_length=5000,
        ignore_permissions=True,
    ):
        rows_by_name[row.name] = row

    for row in frappe.get_all(
        "Client",
        filters={"attending_coach": coach_name},
        fields=CLIENT_FIELDS,
        order_by="full_name asc, name1 asc, last_name asc",
        limit_page_length=5000,
        ignore_permissions=True,
    ):
        rows_by_name[row.name] = row

    return list(rows_by_name.values())


def get_contacts_for_view_coach(coach_name):
    clients = get_clients_for_view_coach(coach_name)

    if not clients:
        return []

    contact_names = get_contact_names_from_clients(
        clients,
        include_billing_contact=True,
    )

    if not contact_names:
        return []

    contacts = frappe.get_all(
        "Contact",
        filters={"name": ["in", contact_names]},
        fields=[
            "name",
            "full_name",
            "first_name",
            "last_name",
            "mobile_no",
            "email_id",
            "designation",
            "company_name",
            "is_billing_contact",
            "custom_customer",
        ],
        order_by="full_name asc, first_name asc, last_name asc",
        limit_page_length=5000,
        ignore_permissions=True,
    )

    rows = []

    for contact in contacts:
        linked_clients = get_linked_clients_for_contact(contact.name, clients)

        if not linked_clients:
            continue

        coach_names = sorted({
            c.get("primary_coach") or c.get("attending_coach")
            for c in linked_clients
            if c.get("primary_coach") or c.get("attending_coach")
        })

        session_worker_names = sorted({
            c.get("session_worker")
            for c in linked_clients
            if c.get("session_worker")
        })

        rows.append({
            "name": contact.name,
            "display_name": get_contact_display_name(contact),
            "mobile_no": contact.get("mobile_no") or "",
            "email_id": contact.get("email_id") or "",
            "designation": contact.get("designation") or "",
            "company_name": contact.get("company_name") or "",
            "is_billing_contact": contact.get("is_billing_contact") or 0,
            "custom_customer": contact.get("custom_customer") or "",
            "linked_clients": linked_clients,
            "linked_client_text": ", ".join([c["display_name"] for c in linked_clients]),
            "coach_name": ", ".join(coach_names),
            "session_worker_name": ", ".join(session_worker_names),
        })

    return dedupe_contacts_prefer_customer(rows)
