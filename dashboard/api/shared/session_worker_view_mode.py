import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.session_workers import get_session_workers
from dashboard.api.shared.clients import CLIENT_FIELDS, normalize_client_row


def get_session_worker_view_mode(scope=None, worker_name=None):
    scope = (scope or "").strip().lower()
    worker_name = (worker_name or "").strip()

    if not worker_name:
        redirect_if_wrong_dashboard("session_worker")
        return {
            "is_view_mode": 0,
            "view_scope": "",
            "view_worker_name": "",
            "view_worker_display_name": "",
            "return_to": "",
            "query_string": "",
        }

    if scope not in ["coach", "franchisor"]:
        frappe.throw(_("Invalid view mode."), frappe.PermissionError)

    data = get_session_workers(scope=scope)

    for worker in data.get("session_workers") or []:
        if worker.get("name") == worker_name:
            return_to = frappe.form_dict.get("return_to") or f"/{scope}_db/session_workers"

            query_string = (
                f"?view_as={worker_name}"
                f"&viewer={scope}"
                f"&return_to={return_to}"
            )

            return {
                "is_view_mode": 1,
                "view_scope": scope,
                "view_worker_name": worker_name,
                "view_worker_display_name": worker.get("display_name") or worker_name,
                "return_to": return_to,
                "query_string": query_string,
            }

    frappe.throw(
        _("You do not have permission to view this session worker."),
        frappe.PermissionError,
    )


def get_clients_for_view_session_worker(worker_name):
    worker_name = (worker_name or "").strip()

    if not worker_name:
        return []

    clients = frappe.get_all(
        "Client",
        filters={"session_worker": worker_name},
        fields=CLIENT_FIELDS,
        order_by="full_name asc",
        limit_page_length=5000,
        ignore_permissions=True,
    )

    return [normalize_client_row(c, include_permissions=False) for c in clients]


def ensure_view_client_access(client_name, worker_name):
    client_name = (client_name or "").strip()
    worker_name = (worker_name or "").strip()

    if not client_name:
        frappe.throw(_("Client not found."))

    if not worker_name:
        frappe.throw(_("Session Worker not found."), frappe.PermissionError)

    client = frappe.get_doc("Client", client_name)

    if client.get("session_worker") != worker_name:
        frappe.throw(
            _("You do not have permission to view this client for this session worker."),
            frappe.PermissionError,
        )

    return client
