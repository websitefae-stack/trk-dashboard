import frappe
from frappe import _

from dashboard.api.shared.client_details import (
    get_client_context_data,
    get_session_worker_name,
)
from dashboard.api.shared.session_worker_view_mode import (
    get_session_worker_view_mode,
    ensure_view_client_access,
)


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    view_as = frappe.form_dict.get("view_as")
    viewer = frappe.form_dict.get("viewer")

    view_mode = get_session_worker_view_mode(
        scope=viewer,
        worker_name=view_as,
    )

    context.no_cache = 1
    context.page_title = "Client Details"
    context.active_page = "clients"
    context.dashboard_notifications_url = "/session_worker_db/notifications"

    context.session_worker_view_mode = view_mode
    context.session_worker_view_query = view_mode.get("query_string") or ""
    context.session_worker_is_view_mode = view_mode.get("is_view_mode") or 0
    context.session_worker_view_return_to = view_mode.get("return_to") or ""
    context.session_worker_view_display_name = view_mode.get("view_worker_display_name") or ""

    if context.session_worker_is_view_mode:
        context.dashboard_user_name = context.session_worker_view_display_name
    else:
        context.dashboard_user_name = get_session_worker_name()

    context.client_details_role = "session_worker"
    context.client_details_base_url = "/session_worker_db"
    context.client_details_api_base = "dashboard.api.shared.client_details"

    if context.session_worker_is_view_mode:
        context.client_details_storage_key = "session_worker_view_client_details_active_tab"
        context.client_details_can_edit = 0
        context.client_details_can_invoice = 0
        context.client_details_can_request_change = 0
    else:
        context.client_details_storage_key = "session_worker_client_details_active_tab"
        context.client_details_can_edit = 0
        context.client_details_can_invoice = 0
        context.client_details_can_request_change = 1

    client_name = frappe.form_dict.get("name")

    if not client_name:
        frappe.throw(_("Client not found."))

    if context.session_worker_is_view_mode:
        ensure_view_client_access(
            client_name=client_name,
            worker_name=view_mode.get("view_worker_name"),
        )

        data = get_client_context_data(
            client_name=client_name,
            is_new=False,
            base_url="/session_worker_db",
            enforce_access=False,
        )
    else:
        data = get_client_context_data(
            client_name=client_name,
            is_new=False,
            base_url="/session_worker_db",
            enforce_access=True,
        )

    for key, value in data.items():
        context[key] = value

    context.client_details_role = "session_worker"
    context.client_details_base_url = "/session_worker_db"
    context.client_details_api_base = "dashboard.api.shared.client_details"

    if context.session_worker_is_view_mode:
        context.client_details_storage_key = "session_worker_view_client_details_active_tab"
        context.client_details_can_edit = 0
        context.client_details_can_invoice = 0
        context.client_details_can_request_change = 0
    else:
        context.client_details_storage_key = "session_worker_client_details_active_tab"
        context.client_details_can_edit = 0
        context.client_details_can_invoice = 0
        context.client_details_can_request_change = 1
