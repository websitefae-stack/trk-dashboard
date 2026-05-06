import frappe
from dashboard.api.shared.contacts import get_contacts_for_scope, ensure_contact_access


@frappe.whitelist()
def get_contacts():
    return get_contacts_for_scope("coach")


def ensure_contact_page_access(contact_name):
    ensure_contact_access(contact_name, "coach")
