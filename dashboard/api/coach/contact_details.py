import frappe
from dashboard.api.shared.contact_details import save_contact_for_scope


@frappe.whitelist()
def save_contact(docname=None, data=None):
    return save_contact_for_scope("coach", docname=docname, data=data)
