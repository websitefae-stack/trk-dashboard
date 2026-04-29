import frappe
from frappe import _
from dashboard.api.franchisor.client_details import (
    get_client_context_data,
    get_franchisor_name,
)


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    context.no_cache = 1
    context.page_title = "Client Details"
    context.active_page = "clients"

    context.dashboard_user_name = get_franchisor_name()
    context.dashboard_notifications_url = "/franchisor_db/notifications"

    client_name = frappe.form_dict.get("name")
    is_new = frappe.form_dict.get("new")

    data = get_client_context_data(
        client_name=client_name,
        is_new=bool(is_new),
        base_url="/franchisor_db",
    )

    for key, value in data.items():
        context[key] = value
