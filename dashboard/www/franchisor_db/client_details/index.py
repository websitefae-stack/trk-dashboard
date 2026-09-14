import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.client_details import (
    get_client_context_data,
    get_franchisor_name,
)
from dashboard.api.shared.school_pipeline import get_school_for_client


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    context.no_cache = 1
    context.page_title = "Client Details"
    context.active_page = "clients"
    context.dashboard_notifications_url = "/franchisor_db/notifications"
    context.dashboard_user_name = get_franchisor_name()

    context.client_details_role = "franchisor"
    context.client_details_base_url = "/franchisor_db"
    context.client_details_api_base = "dashboard.api.shared.client_details"
    context.client_details_storage_key = "franchisor_client_details_active_tab"
    context.client_details_can_edit = 1
    context.client_details_can_invoice = 1
    context.client_details_can_request_change = 0

    client_name = frappe.form_dict.get("name")
    is_new = frappe.form_dict.get("new")

    data = get_client_context_data(
        client_name=client_name,
        is_new=bool(is_new),
        base_url="/franchisor_db",
        enforce_access=False,
    )

    for key, value in data.items():
        context[key] = value

    # Only a client that actually came from (or was linked back to) the
    # School Pipeline gets this tab - most clients aren't schools, so it
    # stays out of the tab list entirely rather than showing up empty on
    # every client record. See school_pipeline.py's module docstring.
    linked_school = get_school_for_client(client_name) if client_name else None
    context.linked_school = linked_school

    if linked_school:
        context.tabs.append({"label": "School Pipeline", "custom": "school_pipeline", "sections": []})
