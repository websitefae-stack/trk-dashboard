import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.coach.client_details import (
    get_client_context_data,
    get_coach_name,
)


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("coach")

    context.no_cache = 1
    context.page_title = "Client Details"
    context.active_page = "clients"

    context.dashboard_user_name = get_coach_name()
    context.dashboard_notifications_url = "/coach_db/notifications"

    client_name = frappe.form_dict.get("name")
    is_new = frappe.form_dict.get("new")

    data = get_client_context_data(
        client_name=client_name,
        is_new=bool(is_new),
        base_url="/coach_db",
    )

    for key, value in data.items():
        context[key] = value
