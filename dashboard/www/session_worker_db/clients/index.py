import frappe
from frappe import _
from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.session_worker.client_details import get_session_worker_name
from trk_session_worker_dashboard.api.clients import _get_allowed_client_names


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("session_worker")

    context.no_cache = 1
    context.page_title = "Clients"
    context.active_page = "clients"
    context.dashboard_notifications_url = "/session_worker_db/notifications"
    context.dashboard_user_name = get_session_worker_name()

    allowed_names = _get_allowed_client_names()

    context.clients = frappe.get_all(
        "Client",
        filters={"name": ["in", allowed_names]} if allowed_names else {"name": ["in", []]},
        fields=[
            "name",
            "name1",
            "last_name",
            "full_name",
            "preferred_name",
            "mobile",
            "email",
            "status",
            "client_type",
            "primary_coach",
            "attending_coach",
            "session_worker",
        ],
        order_by="full_name asc",
        limit_page_length=1000,
    )

    context.client_types = sorted(list({c.get("client_type") for c in context.clients if c.get("client_type")}))

    context.coaches = frappe.get_all(
        "Coach",
        fields=["name", "coach_name"],
        order_by="coach_name asc",
        limit_page_length=500,
    )
