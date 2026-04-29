import frappe
from frappe import _
from dashboard.api.shared.client_details import (
    add_client_note as shared_add_client_note,
    get_client_contacts as shared_get_client_contacts,
    get_client_notes as shared_get_client_notes,
    require_logged_in_user,
)
from trk_session_worker_dashboard.api.clients import (
    _ensure_client_access,
    get_session_worker_display_name,
)


def get_session_worker_name():
    return get_session_worker_display_name()


def ensure_client_access(client_name):
    require_logged_in_user()
    _ensure_client_access(client_name)


@frappe.whitelist()
def get_client_contacts(client_name):
    ensure_client_access(client_name)
    return shared_get_client_contacts(
        client_name=client_name,
        contact_detail_base_url="/session_worker_db/contact_details",
    )


@frappe.whitelist()
def get_client_notes(client_name):
    ensure_client_access(client_name)
    return shared_get_client_notes(client_name)


@frappe.whitelist()
def add_client_note(client_name, note_text, session_date=None, session_type=None):
    ensure_client_access(client_name)
    return shared_add_client_note(
        client_name=client_name,
        note_text=note_text,
        session_date=session_date,
        session_type=session_type,
    )


def get_client_for_context(client_name):
    ensure_client_access(client_name)

    if not frappe.db.exists("Client", client_name):
        frappe.throw(_("Client not found."))

    return frappe.get_doc("Client", client_name)
