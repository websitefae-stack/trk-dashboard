import frappe
from frappe import _

from dashboard.api.shared.client_document_share import get_shared_document_context


def get_context(context):
    context.no_cache = 1
    context.page_title = "Shared Document"

    token = frappe.form_dict.get("token") or ""

    try:
        context.shared_document = get_shared_document_context(token)
        context.link_error = None
    except (frappe.PermissionError, frappe.DoesNotExistError) as e:
        context.shared_document = None
        context.link_error = str(e) or _("This link is invalid.")
