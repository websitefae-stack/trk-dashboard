import frappe
from dashboard.api.shared.contacts import get_contacts_for_scope


@frappe.whitelist()
def get_contacts():
    return get_contacts_for_scope("session_worker")
