import frappe
from frappe import _

from dashboard.api.shared.permissions import (
    redirect_if_wrong_dashboard,
    get_current_coach_name,
)
from dashboard.api.shared.client_details import (
    get_client_context_data,
    get_coach_name,
)
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
    context.page_title = "Client Details"
    context.active_page = "clients"
    context.dashboard_notifications_url = "/coach_db/notifications" + (view_mode.get("query_string") or "")
    context.dashboard_base_url = "/coach_db"

    context.coach_view_mode = view_mode
    context.coach_view_query = view_mode.get("query_string") or ""
    context.coach_is_view_mode = view_mode.get("is_view_mode") or 0
    context.coach_view_return_to = view_mode.get("return_to") or ""
    context.coach_view_display_name = view_mode.get("view_coach_display_name") or ""

    context.client_details_role = "coach"
    context.client_details_base_url = "/coach_db"
    context.client_details_api_base = "dashboard.api.shared.client_details"
    context.client_details_storage_key = "coach_client_details_active_tab"

    client_name = frappe.form_dict.get("name")
    is_new = bool(frappe.form_dict.get("new"))

    if context.coach_is_view_mode:
        context.dashboard_user_name = context.coach_view_display_name
        context.client_details_can_edit = 0
        context.client_details_can_invoice = 0
        context.client_details_can_request_change = 0

        ensure_view_coach_can_access_client(
            client_name=client_name,
            coach_name=view_mode.get("view_coach_name"),
        )

        data = get_client_context_data(
            client_name=client_name,
            is_new=False,
            base_url="/coach_db",
            enforce_access=False,
        )

    else:
        redirect_if_wrong_dashboard("coach")

        context.dashboard_user_name = get_coach_name()
        context.client_details_can_edit = 1
        context.client_details_can_invoice = 1
        context.client_details_can_request_change = 0

        data = get_client_context_data(
            client_name=client_name,
            is_new=is_new,
            base_url="/coach_db",
            enforce_access=True,
            default_primary_coach=get_current_coach_name(optional=True) if is_new else None,
        )

    for key, value in data.items():
        context[key] = value


def ensure_view_coach_can_access_client(client_name, coach_name):
    client_name = (client_name or "").strip()
    coach_name = (coach_name or "").strip()

    if not client_name:
        frappe.throw(_("Client not found."))

    if not coach_name:
        frappe.throw(_("Coach not found."), frappe.PermissionError)

    if not frappe.db.exists("Client", client_name):
        frappe.throw(_("Client not found."))

    client = frappe.db.get_value(
        "Client",
        client_name,
        ["primary_coach", "attending_coach"],
        as_dict=True,
    )

    if not client:
        frappe.throw(_("Client not found."))

    if client.get("primary_coach") != coach_name and client.get("attending_coach") != coach_name:
        frappe.throw(
            _("You do not have permission to view this client for this coach."),
            frappe.PermissionError,
        )
