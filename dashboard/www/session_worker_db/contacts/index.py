import frappe
from frappe import _
from dashboard.api.shared.contacts import get_contacts_for_scope


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    context.no_cache = 1
    context.page_title = "Contacts"
    context.active_page = "contacts"
    context.contacts = get_contacts_for_scope("session_worker")
