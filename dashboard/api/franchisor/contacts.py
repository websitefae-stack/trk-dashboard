import frappe
from dashboard.api.shared.contacts import get_contacts_for_scope, ensure_contact_access


@frappe.whitelist()
def get_contacts(show_all=0, coach_scope="my"):
    return get_contacts_for_scope(
        "franchisor",
        show_all=bool(int(show_all or 0)),
        coach_scope=coach_scope or "my",
    )


def ensure_contact_page_access(contact_name):
    ensure_contact_access(contact_name, "franchisor")
