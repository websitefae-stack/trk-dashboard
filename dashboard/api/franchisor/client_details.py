import frappe
from frappe import _
from dashboard.api.franchisor.clients import get_franchisor_display_name
from dashboard.api.coach.client_details import (
    add_client_note,
    get_client_context_data as coach_get_client_context_data,
    get_link_options,
    save_client,
)


def get_franchisor_name():
    return get_franchisor_display_name()


def get_client_context_data(client_name=None, is_new=False, base_url="/franchisor_db"):
    return coach_get_client_context_data(
        client_name=client_name,
        is_new=is_new,
        base_url=base_url,
        enforce_access=False,
    )
