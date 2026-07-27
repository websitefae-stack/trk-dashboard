import frappe
from frappe import _

from dashboard.api.shared.session_worker_view_mode import get_session_worker_view_mode


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    view_as = frappe.form_dict.get("view_as")
    viewer = frappe.form_dict.get("viewer")

    view_mode = get_session_worker_view_mode(
        scope=viewer,
        worker_name=view_as,
    )

    requirement_name = (frappe.form_dict.get("name") or "").strip()
    practice_document_name = (frappe.form_dict.get("practice_document") or "").strip()

    if not requirement_name and not practice_document_name:
        frappe.local.flags.redirect_location = "/session_worker_db/documents"
        raise frappe.Redirect

    context.no_cache = 1
    context.page_title = "Document"
    context.active_page = "documents"
    context.requirement_name = requirement_name
    context.practice_document_name = practice_document_name

    context.session_worker_view_mode = view_mode
    context.session_worker_view_query = view_mode.get("query_string") or ""
    context.session_worker_is_view_mode = view_mode.get("is_view_mode") or 0
    context.session_worker_view_return_to = view_mode.get("return_to") or ""
    context.session_worker_view_display_name = view_mode.get("view_worker_display_name") or ""

    if context.session_worker_is_view_mode:
        context.dashboard_user_name = context.session_worker_view_display_name
    else:
        context.dashboard_user_name = (
            frappe.get_cached_value("User", frappe.session.user, "full_name")
            or frappe.session.user
        )
