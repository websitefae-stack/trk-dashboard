import frappe
from frappe import _
from dashboard.api.shared.clients import get_client_types
from dashboard.api.session_worker.clients import get_clients, get_session_worker_name


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    context.no_cache = 1
    context.page_title = "Clients"
    context.active_page = "clients"

    try:
        context.session_worker_name = get_session_worker_name()
    except Exception:
        context.session_worker_name = ""

    context.clients = get_clients()
    context.client_types = get_client_types()

    # needed for links
    context.client_detail_base_url = "/session_worker_db/client_details"
