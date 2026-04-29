import frappe
from frappe import _
from dashboard.api.franchisor.clients import get_franchisor_display_name
from dashboard.api.coach.client_details import (
    add_client_note,
    get_client_context_data,
    get_link_options,
    save_client,
)


def get_franchisor_name():
    return get_franchisor_display_name()
