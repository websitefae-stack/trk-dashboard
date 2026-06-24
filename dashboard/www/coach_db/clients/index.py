import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.clients import get_paginated_clients, get_client_types, normalize_client_row, CLIENT_FIELDS
from dashboard.api.shared.directory import get_coach_display_name, get_session_workers
from dashboard.api.shared.coach_view_mode import get_coach_view_mode


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
    context.page_title = "Clients"
    context.active_page = "clients"
    context.dashboard_notifications_url = "/coach_db/notifications" + (view_mode.get("query_string") or "")
    context.dashboard_base_url = "/coach_db"

    context.coach_view_mode = view_mode
    context.coach_view_query = view_mode.get("query_string") or ""
    context.coach_is_view_mode = view_mode.get("is_view_mode") or 0
    context.coach_view_return_to = view_mode.get("return_to") or ""
    context.coach_view_display_name = view_mode.get("view_coach_display_name") or ""

    if context.coach_is_view_mode:
        context.dashboard_user_name = context.coach_view_display_name
        context.clients = get_clients_for_view_coach(view_mode.get("view_coach_name"))
        context.session_workers = get_session_workers_for_view_coach(view_mode.get("view_coach_name"))
    else:
        redirect_if_wrong_dashboard("coach")
        context.dashboard_user_name = get_coach_display_name()
        client_data = get_paginated_clients()
        context.clients = client_data.get("clients", [])
        context.pagination = client_data.get("pagination", {})
        context.search = client_data.get("search", "")
        context.session_workers = get_session_workers()

    context.client_types = get_client_types()


def get_clients_for_view_coach(coach_name):
    coach_name = (coach_name or "").strip()

    if not coach_name:
        return []

    rows_by_name = {}

    for row in frappe.get_all(
        "Client",
        filters={"primary_coach": coach_name},
        fields=CLIENT_FIELDS,
        order_by="full_name asc",
        limit_page_length=5000,
        ignore_permissions=True,
    ):
        rows_by_name[row.name] = row

    for row in frappe.get_all(
        "Client",
        filters={"attending_coach": coach_name},
        fields=CLIENT_FIELDS,
        order_by="full_name asc",
        limit_page_length=5000,
        ignore_permissions=True,
    ):
        rows_by_name[row.name] = row

    return [
        normalize_client_row(row, include_permissions=False)
        for row in sorted(
            rows_by_name.values(),
            key=lambda r: (r.get("full_name") or r.get("name1") or r.get("name") or "").lower(),
        )
    ]


def get_session_workers_for_view_coach(coach_name):
    coach_name = (coach_name or "").strip()

    if not coach_name:
        return []

    client_rows = frappe.get_all(
        "Client",
        filters=[
            ["Client", "primary_coach", "=", coach_name],
            "or",
            ["Client", "attending_coach", "=", coach_name],
        ],
        fields=["session_worker"],
        limit_page_length=5000,
        ignore_permissions=True,
    )

    worker_names = sorted({
        row.get("session_worker")
        for row in client_rows
        if row.get("session_worker")
    })

    if not worker_names:
        return []

    rows = frappe.get_all(
        "Session Worker",
        filters={"name": ["in", worker_names]},
        fields=["name", "sw_name"],
        order_by="sw_name asc",
        limit_page_length=5000,
        ignore_permissions=True,
    )

    return [
        {
            "name": row.name,
            "display_name": row.sw_name or row.name,
        }
        for row in rows
    ]
