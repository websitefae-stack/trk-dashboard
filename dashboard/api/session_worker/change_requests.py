import frappe
from frappe import _
from trk_session_worker_dashboard.api.change_requests import (
    submit_change_request as old_submit_change_request,
    get_client_change_requests as old_get_client_change_requests,
)


@frappe.whitelist()
def submit_change_request(client_name, request_type=None, requested_section=None, requested_change=None, reason=None):
    return old_submit_change_request(
        client_name=client_name,
        request_type=request_type,
        requested_section=requested_section,
        requested_change=requested_change,
        reason=reason,
    )


@frappe.whitelist()
def get_client_change_requests(client_name):
    return old_get_client_change_requests(client_name)
