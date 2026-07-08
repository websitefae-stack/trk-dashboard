import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.contacts import (
    get_contacts_for_scope,
    get_paginated_contacts_for_scope,
    get_current_coach_name,
    get_contact_rows_for_clients,
)
from dashboard.api.shared.coach_view_mode import get_coach_view_mode
from dashboard.api.shared.pagination import make_pagination


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

    context.view_mode_active = context.coach_is_view_mode
    context.view_mode_label = "Coach"
    context.view_mode_display_name = context.coach_view_display_name
    context.view_mode_return_to = context.coach_view_return_to
    context.view_mode_back_label = "Coaches"

    if context.coach_is_view_mode:
        context.dashboard_user_name = context.coach_view_display_name
        context.contacts = get_contacts_for_view_coach(view_mode.get("view_coach_name"))
        # View mode loads every matching row at once (no server-side
        # pagination), so this is just a single-page pagination object -
        # the shared pagination template still needs one to render.
        context.pagination = make_pagination(len(context.contacts), 1, max(len(context.contacts), 1))
        context.search = ""
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
    return get_contact_rows_for_clients(clients, scope="coach")
