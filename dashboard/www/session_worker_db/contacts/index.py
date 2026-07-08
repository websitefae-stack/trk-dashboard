import frappe
from frappe import _

from dashboard.api.shared.contacts import (
    get_contacts_for_scope,
    get_paginated_contacts_for_scope,
    get_contact_rows_for_clients,
)
from dashboard.api.shared.session_worker_view_mode import get_session_worker_view_mode
from dashboard.api.shared.permissions import is_franchisor_user
from dashboard.api.shared.pagination import make_pagination


def get_current_coach_name():
    if not frappe.db.exists("DocType", "Coach"):
        return ""

    meta = frappe.get_meta("Coach")

    for fieldname in ["user", "user_id", "email", "coach_email"]:
        if meta.has_field(fieldname):
            coach = frappe.db.get_value(
                "Coach",
                {fieldname: frappe.session.user},
                "name",
            )

            if coach:
                return coach

    return ""


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    view_as = frappe.form_dict.get("view_as")
    viewer = frappe.form_dict.get("viewer")

    view_mode = get_session_worker_view_mode(
        scope=viewer,
        worker_name=view_as,
    )

    viewer_scope = (viewer or "").strip().lower()

    context.no_cache = 1
    context.page_title = "Contacts"
    context.active_page = "contacts"
    context.dashboard_notifications_url = "/session_worker_db/notifications" + (view_mode.get("query_string") or "")

    context.session_worker_view_mode = view_mode
    context.session_worker_view_query = view_mode.get("query_string") or ""
    context.session_worker_is_view_mode = view_mode.get("is_view_mode") or 0
    context.session_worker_view_return_to = view_mode.get("return_to") or ""
    context.session_worker_view_display_name = view_mode.get("view_worker_display_name") or ""

    context.view_mode_active = context.session_worker_is_view_mode
    context.view_mode_label = "Session Worker"
    context.view_mode_display_name = context.session_worker_view_display_name
    context.view_mode_return_to = context.session_worker_view_return_to
    context.view_mode_back_label = "Session Workers"

    context.viewer_scope = viewer_scope
    context.viewer_coach_name = ""

    viewer_is_franchisor = viewer_scope in ["franchisor", "admin"] or is_franchisor_user()

    if context.session_worker_is_view_mode:
        context.dashboard_user_name = context.session_worker_view_display_name

        contacts = get_contacts_for_view_session_worker(
            view_mode.get("view_worker_name")
        )

        if viewer_is_franchisor:
            context.contacts = mark_all_contacts_viewable(contacts)
        else:
            context.viewer_coach_name = get_current_coach_name()
            context.contacts = mark_contacts_for_coach_view(
                contacts,
                context.viewer_coach_name,
            )

        # View mode loads every matching row at once (no server-side
        # pagination), so this is just a single-page pagination object -
        # the shared pagination template still needs one to render.
        context.pagination = make_pagination(len(context.contacts), 1, max(len(context.contacts), 1))
        context.search = ""

    else:
        context.dashboard_user_name = frappe.db.get_value(
            "Session Worker",
            {"user": frappe.session.user},
            "sw_name",
        ) or frappe.session.user

        contact_data = get_paginated_contacts_for_scope("session_worker")
        contacts = contact_data.get("contacts", [])
        context.contacts = mark_all_contacts_viewable(contacts)
        context.pagination = contact_data.get("pagination", {})
        context.search = contact_data.get("search", "")


def mark_all_contacts_viewable(contacts):
    for contact in contacts or []:
        contact["can_view_contact"] = 1

    return contacts or []


def mark_contacts_for_coach_view(contacts, coach_name):
    coach_name = (coach_name or "").strip()

    for contact in contacts or []:
        can_view = 0

        if coach_name:
            for linked_client in contact.get("linked_clients") or []:
                if (
                    linked_client.get("primary_coach") == coach_name
                    or linked_client.get("attending_coach") == coach_name
                ):
                    can_view = 1
                    break

        contact["can_view_contact"] = can_view

    return contacts or []


def get_contacts_for_view_session_worker(worker_name):
    worker_name = (worker_name or "").strip()

    if not worker_name:
        return []

    clients = frappe.get_all(
        "Client",
        filters={"session_worker": worker_name},
        fields=[
            "name", "full_name", "name1", "last_name",
            "status", "client_type",
            "primary_coach", "attending_coach", "session_worker",
            "billing_contact",
        ],
        order_by="full_name asc, name1 asc, last_name asc",
        limit_page_length=5000,
        ignore_permissions=True,
    )

    rows = get_contact_rows_for_clients(clients, scope="session_worker")

    for row in rows:
        row.setdefault("can_view_contact", 0)

    return rows
